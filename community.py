import hashlib
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from extensions import db


GARDEN_TYPES = ("interior", "exterior", "balcon", "terraza", "otro")
PLANT_CATEGORIES = ("Hortaliza", "Aromática", "Fruta", "Ornamental", "Flor", "Otra")
PRIVATE_DETAIL_PATTERN = re.compile(
    r"(?:[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\+?\d[\d\s().-]{7,}\d|"
    r"\b(?:calle|calz(?:ada)?|avenida|av\.?|privada|andador|carretera|c\.?p\.?)\b|"
    r"\b(?:casa|departamento|depto|n[uú]mero|no\.?|#)\s*\w*\s*\d+)",
    re.IGNORECASE,
)
ALLOWED_PHOTO_TYPES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}
CITY_CENTERS = {
    "aguascalientes": (21.8853, -102.2916),
    "campeche": (19.8301, -90.5349),
    "cancun": (21.1619, -86.8515),
    "chihuahua": (28.6353, -106.0889),
    "ciudad de mexico": (19.4326, -99.1332),
    "cdmx": (19.4326, -99.1332),
    "ciudad juarez": (31.6904, -106.4245),
    "guadalajara": (20.6597, -103.3496),
    "hermosillo": (29.0729, -110.9559),
    "leon": (21.1221, -101.6827),
    "merida": (20.9674, -89.5926),
    "mexicali": (32.6245, -115.4523),
    "monterrey": (25.6866, -100.3161),
    "morelia": (19.7008, -101.1844),
    "oaxaca": (17.0732, -96.7266),
    "puebla": (19.0414, -98.2063),
    "queretaro": (20.5888, -100.3899),
    "san luis potosi": (22.1565, -100.9855),
    "tijuana": (32.5149, -117.0382),
    "toluca": (19.2826, -99.6557),
    "veracruz": (19.1738, -96.1342),
}


class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    category = db.Column(db.String(80), nullable=False, default="Otra")
    description = db.Column(db.String(300), nullable=False, default="")
    gardens = db.relationship("GardenPlant", back_populates="plant", cascade="all, delete-orphan")


class Garden(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    alias = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    approximate_zone = db.Column(db.String(120), nullable=False)
    public_lat = db.Column(db.Float)
    public_lng = db.Column(db.Float)
    garden_type = db.Column(db.String(20), nullable=False)
    photo_path = db.Column(db.String(255))
    share_seeds = db.Column(db.Boolean, nullable=False, default=False)
    share_cuttings = db.Column(db.Boolean, nullable=False, default=False)
    share_advice = db.Column(db.Boolean, nullable=False, default=False)
    visible_map = db.Column(db.Boolean, nullable=False, default=False)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    owner = db.relationship("User")
    plants = db.relationship("GardenPlant", back_populates="garden", cascade="all, delete-orphan")


class GardenPlant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey("garden.id"), nullable=False)
    plant_id = db.Column(db.Integer, db.ForeignKey("plant.id"), nullable=False)
    approximate_quantity = db.Column(db.String(40), nullable=False, default="")
    garden = db.relationship("Garden", back_populates="plants")
    plant = db.relationship("Plant", back_populates="gardens")
    __table_args__ = (db.UniqueConstraint("garden_id", "plant_id", name="uq_garden_plant"),)


def normalized_place(value):
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in value if not unicodedata.combining(char)).casefold().strip()


def approximate_coordinates(city, salt):
    center = CITY_CENTERS.get(normalized_place(city))
    if center is None:
        return None, None
    digest = hashlib.blake2b(str(salt).encode("utf-8"), digest_size=4).digest()
    lat_offset = (int.from_bytes(digest[:2], "big") / 65535 - 0.5) * 0.04
    lng_offset = (int.from_bytes(digest[2:], "big") / 65535 - 0.5) * 0.04
    return round(center[0] + lat_offset, 2), round(center[1] + lng_offset, 2)


def submitted_checkbox(name):
    return request.form.get(name) == "yes"


def save_garden_photo(upload):
    if upload is None or not upload.filename:
        return None
    filename = secure_filename(upload.filename)
    extension = Path(filename).suffix.lower()
    signatures = ALLOWED_PHOTO_TYPES.get(extension)
    if not filename or not signatures:
        raise ValueError("La fotografía debe ser JPG, PNG o WebP.")
    header = upload.stream.read(12)
    upload.stream.seek(0)
    valid_signature = any(header.startswith(signature) for signature in signatures)
    if extension == ".webp":
        valid_signature = header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if not valid_signature:
        raise ValueError("El archivo no parece ser una imagen JPG, PNG o WebP válida.")
    upload_dir = Path(current_app.root_path) / "static" / "uploads" / "gardens"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = "{}{}".format(uuid.uuid4().hex, extension)
    upload.save(upload_dir / stored_name)
    return "uploads/gardens/{}".format(stored_name)


def register_community_routes(app):
    @app.route("/map")
    def community_map():
        categories = [
            row[0]
            for row in db.session.query(Plant.category)
            .join(GardenPlant)
            .join(Garden)
            .filter(Garden.visible_map.is_(True))
            .distinct()
            .order_by(Plant.category)
            .all()
        ]
        places = sorted({
            "{} · {}".format(garden.city, garden.approximate_zone)
            for garden in Garden.query.filter_by(visible_map=True).all()
        })
        return render_template(
            "map.html",
            title="Comunidad | Raíz",
            plant_categories=categories,
            garden_types=GARDEN_TYPES,
            garden_type_labels={
                "interior": "Interior",
                "exterior": "Exterior",
                "balcon": "Balcón",
                "terraza": "Terraza",
                "otro": "Otro",
            },
            places=places,
        )

    @app.get("/api/community-data")
    def community_data():
        query = Garden.query.filter(
            Garden.visible_map.is_(True),
            Garden.public_lat.isnot(None),
            Garden.public_lng.isnot(None),
        )
        plant_name = request.args.get("plant", "").strip()[:80]
        plant_category = request.args.get("category", "").strip()
        garden_type = request.args.get("type", "").strip()
        place = request.args.get("place", "").strip()
        if plant_name:
            query = query.filter(
                Garden.plants.any(GardenPlant.plant.has(Plant.name.ilike("%{}%".format(plant_name))))
            )
        if plant_category in PLANT_CATEGORIES:
            query = query.filter(
                Garden.plants.any(GardenPlant.plant.has(Plant.category == plant_category))
            )
        if garden_type in GARDEN_TYPES:
            query = query.filter(Garden.garden_type == garden_type)
        if place:
            city, separator, zone = place.partition(" · ")
            if separator:
                query = query.filter(Garden.city == city, Garden.approximate_zone == zone)
        if request.args.get("seeds") == "1":
            query = query.filter(Garden.share_seeds.is_(True))
        if request.args.get("cuttings") == "1":
            query = query.filter(Garden.share_cuttings.is_(True))
        gardens = query.distinct().order_by(Garden.created_at.desc()).all()
        return jsonify([
            {
                "id": garden.id,
                "name": garden.name,
                "alias": garden.alias,
                "description": garden.description,
                "city": garden.city,
                "zone": garden.approximate_zone,
                "lat": garden.public_lat,
                "lng": garden.public_lng,
                "type": garden.garden_type,
                "photo": url_for("static", filename=garden.photo_path) if garden.photo_path else None,
                "plants": [
                    {"name": relation.plant.name, "category": relation.plant.category}
                    for relation in garden.plants
                ],
                "share_seeds": garden.share_seeds,
                "share_cuttings": garden.share_cuttings,
                "share_advice": garden.share_advice,
                "is_demo": garden.is_demo,
                "profile": url_for("garden_profile", garden_id=garden.id),
            }
            for garden in gardens
        ])

    @app.route("/community/gardens/new", methods=["GET", "POST"])
    @login_required
    def new_garden():
        purchased_seeds = {
            item.seed_id: item.seed
            for order in current_user.orders
            for item in order.items
            if item.seed is not None
        }
        selected_seed_ids = []
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            alias = request.form.get("alias", "").strip()
            description = request.form.get("description", "").strip()
            city = request.form.get("city", "").strip()
            zone = request.form.get("approximate_zone", "").strip()
            garden_type = request.form.get("garden_type", "").strip()
            submitted_seed_ids = request.form.getlist("plants")
            try:
                selected_seed_ids = list(dict.fromkeys(int(seed_id) for seed_id in submitted_seed_ids))
            except ValueError:
                selected_seed_ids = []
            quantity = request.form.get("approximate_quantity", "").strip()
            visible = submitted_checkbox("visible_map")

            validation_error = None
            if not (2 <= len(name) <= 120 and 2 <= len(alias) <= 80 and 10 <= len(description) <= 500):
                validation_error = "Revisa el nombre, alias y descripción (la descripción debe tener al menos 10 caracteres)."
            elif not (2 <= len(city) <= 120 and 2 <= len(zone) <= 120):
                validation_error = "Indica una ciudad y una zona aproximada."
            elif any(PRIVATE_DETAIL_PATTERN.search(value) for value in (name, alias, zone, description)):
                validation_error = "Los datos públicos no pueden incluir correos, teléfonos ni detalles de domicilios."
            elif garden_type not in GARDEN_TYPES:
                validation_error = "Selecciona un tipo de huerto válido."
            elif not purchased_seeds:
                validation_error = "Necesitas comprar al menos una semilla del catálogo antes de registrar un huerto."
            elif len(submitted_seed_ids) != len(selected_seed_ids) or not selected_seed_ids:
                validation_error = "Selecciona al menos una planta del catálogo que hayas comprado."
            elif len(selected_seed_ids) > 20 or any(seed_id not in purchased_seeds for seed_id in selected_seed_ids):
                validation_error = "Solo puedes agregar plantas del catálogo que hayas comprado."
            elif len(quantity) > 40:
                validation_error = "La cantidad aproximada no puede exceder 40 caracteres."
            elif visible and CITY_CENTERS.get(normalized_place(city)) is None:
                validation_error = "Aún no podemos ubicar esa ciudad de forma aproximada. Desactiva su aparición en el mapa o selecciona una ciudad compatible."

            photo_path = None
            if validation_error is None:
                try:
                    photo_path = save_garden_photo(request.files.get("photo"))
                except ValueError as error:
                    validation_error = str(error)

            if validation_error:
                flash(validation_error, "error")
            else:
                garden = Garden(
                    owner_id=current_user.id,
                    name=name,
                    alias=alias,
                    description=description,
                    city=city,
                    approximate_zone=zone,
                    garden_type=garden_type,
                    photo_path=photo_path,
                    share_seeds=submitted_checkbox("share_seeds"),
                    share_cuttings=submitted_checkbox("share_cuttings"),
                    share_advice=submitted_checkbox("share_advice"),
                    visible_map=visible,
                )
                if visible:
                    garden.public_lat, garden.public_lng = approximate_coordinates(
                        city, "{}-{}".format(current_user.id, zone)
                    )
                db.session.add(garden)
                db.session.flush()
                for seed_id in selected_seed_ids:
                    seed = purchased_seeds[seed_id]
                    plant = Plant.query.filter(db.func.lower(Plant.name) == seed.name.lower()).first()
                    if plant is None:
                        plant = Plant(name=seed.name, category=seed.category)
                        db.session.add(plant)
                        db.session.flush()
                    garden.plants.append(GardenPlant(plant=plant, approximate_quantity=quantity))
                db.session.commit()
                flash("Tu huerto quedó guardado. Puedes cambiar su visibilidad desde su perfil.", "success")
                return redirect(url_for("garden_profile", garden_id=garden.id))
        return render_template(
            "garden_form.html",
            title="Registrar huerto | Raíz",
            garden_types=GARDEN_TYPES,
            garden_type_labels={
                "interior": "Interior",
                "exterior": "Exterior",
                "balcon": "Balcón",
                "terraza": "Terraza",
                "otro": "Otro",
            },
            purchased_seeds=sorted(purchased_seeds.values(), key=lambda seed: seed.name.casefold()),
            selected_seed_ids=selected_seed_ids,
        )

    @app.get("/community/gardens/<int:garden_id>")
    def garden_profile(garden_id):
        garden = db.session.get(Garden, garden_id)
        if garden is None or (
            not garden.visible_map and (
                not current_user.is_authenticated or current_user.id != garden.owner_id
            )
        ):
            abort(404)
        return render_template(
            "garden_profile.html",
            title="{} | Comunidad Raíz".format(garden.name),
            garden=garden,
        )

    @app.post("/community/gardens/<int:garden_id>/visibility")
    @login_required
    def toggle_garden_visibility(garden_id):
        garden = db.session.get(Garden, garden_id)
        if garden is None or garden.owner_id != current_user.id:
            abort(404)
        garden.visible_map = submitted_checkbox("visible_map")
        if garden.visible_map:
            coordinates = approximate_coordinates(
                garden.city, "{}-{}".format(current_user.id, garden.approximate_zone)
            )
            if coordinates == (None, None):
                garden.visible_map = False
                db.session.commit()
                flash(
                    "No se pudo publicar el huerto porque la ciudad no tiene una ubicación aproximada disponible.",
                    "error",
                )
                return redirect(url_for("garden_profile", garden_id=garden.id))
            garden.public_lat, garden.public_lng = coordinates
        else:
            garden.public_lat = None
            garden.public_lng = None
        db.session.commit()
        flash("Visibilidad del huerto actualizada.", "success")
        return redirect(url_for("garden_profile", garden_id=garden.id))
