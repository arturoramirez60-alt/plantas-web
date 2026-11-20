import json
import hmac
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from community import Garden, GardenPlant, Plant, approximate_coordinates, register_community_routes
from extensions import db

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///" + str(BASE_DIR / "database.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
DEMO_MODE = os.environ.get("DEMO_MODE", "1").lower() not in {"0", "false", "no"}

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Inicia sesión para continuar."
login_manager.login_message_category = "info"

KIT_TYPES = ("starter", "refill", "seed_only")
KIT_LABELS = {
    "starter": "Kit Inicio",
    "refill": "Kit Recarga",
    "seed_only": "Solo Semillas",
}
PRODUCT_IMAGES = {
    "Jitomate Cherry": {
        "refill": "01_Kit_Tomate_Cherry_Estudio.png",
        "starter": "02_Kit_Tomate_Cherry_Pala_y_Guantes.png",
        "seed_only": "03_Sobre_Tomate_Cherry_Frontal.png",
    },
    "Albahaca": {
        "refill": "04_Kit_Albahaca_Estudio.png",
        "starter": "05_Kit_Albahaca_Pala_y_Guantes.png",
        "seed_only": "06_Sobre_Albahaca_Frontal.png",
    },
    "Manzanilla": {
        "refill": "07_Kit_Manzanilla_Estudio.png",
        "starter": "08_Kit_Manzanilla_Pala_y_Guantes.png",
        "seed_only": "09_Sobre_Manzanilla_Frontal.png",
    },
    "Lechuga": {
        "refill": "10_Kit_Lechuga_Estudio.png",
        "starter": "11_Kit_Lechuga_Pala_y_Guantes.png",
        "seed_only": "12_Sobre_Lechuga_Frontal.png",
    },
    "Chile Serrano": {
        "refill": "13_Kit_Chile_Serrano_Estudio.png",
        "starter": "14_Kit_Chile_Serrano_Pala_y_Guantes.png",
        "seed_only": "15_Sobre_Chile_Serrano_Frontal.png",
    },
}
CARE_VIDEO_QUERIES = {
    "Jitomate Cherry": "como cuidar jitomate cherry maceta",
    "Albahaca": "como cuidar albahaca maceta",
    "Manzanilla": "como cuidar manzanilla maceta",
    "Lechuga": "como cultivar lechuga maceta",
    "Chile Serrano": "como cuidar chile serrano maceta",
    "Menta": "como cuidar menta maceta",
    "Fresa": "como cuidar fresas maceta",
    "Limón": "como cuidar limonero maceta",
}
SOIL_PRICE = 85
FERTILIZER_PRICE = 55
TOOLS_PRICE = 120


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    city = db.Column(db.String(120), default="")
    community_opt_in = db.Column(db.Boolean, nullable=False, default=False)
    orders = db.relationship("Order", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Seed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    category = db.Column(db.String(80), nullable=False)
    pot_size = db.Column(db.String(40), nullable=False)
    tools_needed = db.Column(db.Text, nullable=False, default="[]")
    price = db.Column(db.Integer, nullable=False)
    care_guide = db.Column(db.Text, nullable=False)

    @property
    def tools(self):
        try:
            return json.loads(self.tools_needed)
        except (TypeError, json.JSONDecodeError):
            return []

    @property
    def guide_steps(self):
        return [line.strip() for line in self.care_guide.splitlines() if line.strip()]

    @property
    def care_video_url(self):
        query = CARE_VIDEO_QUERIES.get(self.name, "como cuidar plantas en maceta {}".format(self.name))
        return "https://www.youtube.com/results?search_query={}".format(quote_plus(query))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total = db.Column(db.Integer, nullable=False, default=0)
    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    seed_id = db.Column(db.Integer, db.ForeignKey("seed.id"), nullable=False)
    kit_type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    order = db.relationship("Order", back_populates="items")
    seed = db.relationship("Seed")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def pot_price(pot_size):
    match = re.search(r"\d+", pot_size or "")
    diameter = int(match.group()) if match else 18
    if diameter <= 12:
        return 65
    if diameter <= 18:
        return 90
    return 130


def kit_breakdown(seed, kit_type):
    if kit_type not in KIT_TYPES:
        raise ValueError("Tipo de kit no válido")
    items = ["Sobre de semillas"]
    total = seed.price
    if kit_type != "seed_only":
        items.extend(["Maceta de {}".format(seed.pot_size), "Tierra preparada", "Abono orgánico"])
        total += pot_price(seed.pot_size) + SOIL_PRICE + FERTILIZER_PRICE
    if kit_type == "starter":
        tools = seed.tools
        if tools:
            items.extend(tools)
            total += TOOLS_PRICE
    return {"label": KIT_LABELS[kit_type], "items": items, "price": total}


def catalog_payload(seeds):
    return [
        {
            "id": seed.id,
            "name": seed.name,
            "category": seed.category,
            "pot_size": seed.pot_size,
            "tools": seed.tools,
            "price": effective_price(seed.price),
            "prices": {kind: effective_price(kit_breakdown(seed, kind)["price"]) for kind in KIT_TYPES},
            "contents": {kind: kit_breakdown(seed, kind)["items"] for kind in KIT_TYPES},
        }
        for seed in seeds
    ]


def get_cart():
    cart = session.get("cart", [])
    clean_cart = []
    for item in cart:
        try:
            seed_id = int(item["seed_id"])
            kit_type = item["kit_type"]
            quantity = max(1, min(20, int(item.get("quantity", 1))))
        except (KeyError, TypeError, ValueError):
            continue
        if kit_type in KIT_TYPES:
            clean_cart.append({"seed_id": seed_id, "kit_type": kit_type, "quantity": quantity})
    return clean_cart


def cart_details():
    details = []
    total = 0
    for item in get_cart():
        seed = db.session.get(Seed, item["seed_id"])
        if seed is None:
            continue
        kit = dict(kit_breakdown(seed, item["kit_type"]))
        kit["price"] = effective_price(kit["price"])
        line_total = kit["price"] * item["quantity"]
        details.append({"seed": seed, "kit_type": item["kit_type"], "kit": kit, "quantity": item["quantity"], "line_total": line_total})
        total += line_total
    return details, total


def effective_price(price):
    return 0 if DEMO_MODE else price


def safe_local_redirect(target, fallback):
    if target:
        parsed = urlparse(target)
        if not parsed.netloc and target.startswith("/") and not target.startswith("//"):
            return target
    return fallback


@app.context_processor
def inject_cart_count():
    return {
        "cart_count": sum(item["quantity"] for item in get_cart()),
        "kit_labels": KIT_LABELS,
        "kit_types": KIT_TYPES,
        "kit_breakdown": kit_breakdown,
        "demo_mode": DEMO_MODE,
    }


@app.context_processor
def inject_csrf_token():
    def csrf_token():
        token = session.get("_csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token
    return {"csrf_token": csrf_token}


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        expected = session.get("_csrf_token", "")
        supplied = request.form.get("_csrf_token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            abort(400, description="Token de formulario inválido. Recarga la página e inténtalo de nuevo.")


@app.route("/")
def index():
    seeds = Seed.query.order_by(Seed.id).all()
    return render_template("index.html", title="Raíz | Cultiva en casa", seeds=seeds, seed_data=catalog_payload(seeds))


@app.route("/catalog")
def catalog():
    seeds = Seed.query.order_by(Seed.id).all()
    return render_template(
        "catalog.html",
        title="Catálogo | Raíz",
        seeds=seeds,
        seed_data=catalog_payload(seeds),
        product_images=PRODUCT_IMAGES,
    )


@app.route("/imagenes/<path:filename>")
def product_image(filename):
    return send_from_directory(BASE_DIR / "imagenes", filename)


@app.post("/cart/add")
def add_to_cart():
    try:
        seed_id = int(request.form.get("seed_id", ""))
        quantity = max(1, min(20, int(request.form.get("quantity", "1"))))
    except ValueError:
        abort(400)
    kit_type = request.form.get("kit_type", "")
    if kit_type not in KIT_TYPES or db.session.get(Seed, seed_id) is None:
        abort(400)
    cart = get_cart()
    existing = next((item for item in cart if item["seed_id"] == seed_id and item["kit_type"] == kit_type), None)
    if existing:
        existing["quantity"] = min(20, existing["quantity"] + quantity)
    else:
        cart.append({"seed_id": seed_id, "kit_type": kit_type, "quantity": quantity})
    session["cart"] = cart
    flash("Añadido al carrito.", "success")
    return redirect(safe_local_redirect(request.form.get("next"), url_for("cart")))


@app.route("/cart", methods=["GET", "POST"])
def cart():
    if request.method == "POST":
        updated = []
        for item in get_cart():
            quantity_key = "quantity_{}_{}".format(item["seed_id"], item["kit_type"])
            try:
                quantity = int(request.form.get(quantity_key, item["quantity"]))
            except ValueError:
                quantity = item["quantity"]
            if quantity > 0:
                item["quantity"] = min(20, quantity)
                updated.append(item)
        session["cart"] = updated
        flash("Carrito actualizado.", "success")
        return redirect(url_for("cart"))
    details, total = cart_details()
    return render_template("cart.html", title="Tu carrito | Raíz", items=details, total=total)


@app.post("/cart/remove/<int:seed_id>/<kit_type>")
def remove_from_cart(seed_id, kit_type):
    session["cart"] = [item for item in get_cart() if not (item["seed_id"] == seed_id and item["kit_type"] == kit_type)]
    flash("Producto eliminado del carrito.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items, total = cart_details()
    if not items:
        flash("Agrega un kit antes de finalizar tu pedido.", "info")
        return redirect(url_for("catalog"))
    if request.method == "POST":
        order = Order(user_id=current_user.id, total=total)
        for item in items:
            order.items.append(OrderItem(
                seed_id=item["seed"].id,
                kit_type=item["kit_type"],
                quantity=item["quantity"],
                unit_price=item["kit"]["price"],
            ))
        db.session.add(order)
        db.session.commit()
        session["cart"] = []
        flash("Pedido #{} confirmado. Recuerda que este prototipo no procesa pagos.".format(order.id), "success")
        return redirect(url_for("my_plants"))
    return render_template("checkout.html", title="Finalizar pedido | Raíz", items=items, total=total)


@app.route("/my-plants")
@login_required
def my_plants():
    purchased = (
        OrderItem.query.join(Order).filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc(), OrderItem.id.desc()).all()
    )
    gardens = Garden.query.filter_by(owner_id=current_user.id).order_by(Garden.created_at.desc()).all()
    return render_template("my_plants.html", title="Mis plantas | Raíz", items=purchased, gardens=gardens)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("my_plants"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Qué gusto verte, {}.".format(user.username), "success")
            return redirect(safe_local_redirect(request.args.get("next"), url_for("my_plants")))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("login.html", title="Iniciar sesión | Raíz")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("my_plants"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        city = request.form.get("city", "").strip()
        if len(username) < 3 or "@" not in email or len(password) < 8:
            flash("Usa un nombre de al menos 3 caracteres, un correo válido y una contraseña de 8 caracteres.", "error")
        elif User.query.filter(db.or_(User.username == username, User.email == email)).first():
            flash("Ese nombre o correo ya está registrado.", "error")
        else:
            user = User(username=username, email=email, city=city)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Tu cuenta está lista. ¡A cultivar!", "success")
            return redirect(url_for("my_plants"))
    return render_template("register.html", title="Crear cuenta | Raíz")


@app.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("index"))


register_community_routes(app)


def initialize_database():
    with app.app_context():
        db.create_all()
        if Seed.query.count() == 0:
            seed_data = [
                ("Jitomate Cherry", "Hortaliza", "maceta de 30 cm", ["Pala de mano", "Guantes"], 95,
                 "01. Siembra a 0.5 cm de profundidad y conserva la tierra húmeda.\n02. Coloca la maceta donde reciba al menos 6 horas de sol.\n03. Riega cuando la superficie de la tierra comience a secarse.\n04. Entutora el tallo y cosecha los frutos cuando estén rojos y firmes."),
                ("Albahaca", "Aromática", "maceta de 18 cm", ["Pala de mano", "Tijeras de poda"], 65,
                 "01. Cubre ligeramente las semillas con sustrato.\n02. Busca un sitio cálido con 4 a 6 horas de luz.\n03. Mantén la tierra ligeramente húmeda, sin encharcar.\n04. Corta las puntas con frecuencia para estimular nuevas hojas."),
                ("Manzanilla", "Flor", "maceta de 18 cm", ["Pala de mano"], 70,
                 "01. Esparce las semillas sobre la superficie sin cubrirlas demasiado.\n02. Colócala en un sitio soleado y ventilado.\n03. Riega suavemente cuando la capa superior esté seca.\n04. Cosecha las flores abiertas y déjalas secar a la sombra."),
                ("Lechuga", "Hortaliza", "maceta de 20 cm", ["Pala de mano", "Regadera"], 60,
                 "01. Siembra a poca profundidad y deja espacio entre semillas.\n02. Dale luz abundante, evitando el calor intenso del mediodía.\n03. Riega seguido para mantener humedad constante.\n04. Corta las hojas exteriores cuando tengan buen tamaño."),
                ("Chile Serrano", "Hortaliza", "maceta de 25 cm", ["Pala de mano", "Guantes"], 85,
                 "01. Siembra en sustrato tibio y cubre con una capa fina de tierra.\n02. Asegura al menos 6 horas de sol directo.\n03. Riega profundamente cuando la superficie se sienta seca.\n04. Cosecha los chiles verdes y firmes con tijeras limpias."),
            ]
            db.session.add_all([
                Seed(name=name, category=category, pot_size=pot, tools_needed=json.dumps(tools), price=price, care_guide=guide)
                for name, category, pot, tools, price, guide in seed_data
            ])
            db.session.commit()

        demo_users = [
            ("Sofía", "sofia@raiz.demo", "Ciudad de México", 19.4326, -99.1332),
            ("Mateo", "mateo@raiz.demo", "Guadalajara", 20.6597, -103.3496),
            ("Lucía", "lucia@raiz.demo", "Ciudad de México", 19.3890, -99.1600),
        ]
        for username, email, city, lat, lng in demo_users:
            user = User.query.filter_by(email=email).first()
            if user is None:
                user = User(username=username, email=email, city=city, lat=lat, lng=lng, community_opt_in=True)
                user.set_password("raizdemo")
                db.session.add(user)
                db.session.flush()
            if not Order.query.filter_by(user_id=user.id).first():
                seeds = Seed.query.order_by(Seed.id).all()
                chosen = seeds[:2] if username != "Mateo" else seeds[2:4]
                order = Order(user_id=user.id, total=sum(kit_breakdown(seed, "starter")["price"] for seed in chosen))
                for seed in chosen:
                    order.items.append(OrderItem(seed=seed, kit_type="starter", quantity=1,
                                                 unit_price=kit_breakdown(seed, "starter")["price"]))
                db.session.add(order)
        db.session.commit()
        if Garden.query.count() == 0:
            garden_demos = [
                ("El cantero de Sofía (DEMO)", "Sofía · perfil ficticio", "Hortalizas de temporada en macetas; datos ficticios para probar el mapa.", "Ciudad de México", "Zona centro (aproximada)", "balcon", "Jitomate Cherry, Lechuga", "Hortaliza", True, False, True),
                ("Hierbas de Mateo (DEMO)", "Mateo · perfil ficticio", "Un pequeño espacio de aromáticas para cocinar y compartir esquejes.", "Guadalajara", "Zona centro (aproximada)", "terraza", "Albahaca, Menta", "Aromática", True, True, True),
                ("Frutitas de Lucía (DEMO)", "Lucía · perfil ficticio", "Frutales en contenedor y notas para cuidarlos en espacios pequeños.", "Ciudad de México", "Zona sur (aproximada)", "exterior", "Fresa, Limón", "Fruta", False, True, True),
                ("Selva de ventana (DEMO)", "Sofía · perfil ficticio", "Plantas ornamentales resistentes y propagación en agua.", "Ciudad de México", "Zona norte (aproximada)", "interior", "Poto, Monstera", "Ornamental", False, True, False),
            ]
            for name, alias, description, city, zone, kind, plant_list, category, seeds, cuttings, advice in garden_demos:
                owner = User.query.filter_by(username=alias.split(" ·", 1)[0]).first()
                garden = Garden(
                    owner_id=owner.id,
                    name=name,
                    alias=alias,
                    description=description,
                    city=city,
                    approximate_zone=zone,
                    garden_type=kind,
                    share_seeds=seeds,
                    share_cuttings=cuttings,
                    share_advice=advice,
                    visible_map=True,
                    is_demo=True,
                )
                garden.public_lat, garden.public_lng = approximate_coordinates(city, name)
                db.session.add(garden)
                for plant_name in plant_list.split(", "):
                    plant = Plant.query.filter_by(name=plant_name).first()
                    if plant is None:
                        plant = Plant(name=plant_name, category=category)
                        db.session.add(plant)
                        db.session.flush()
                    garden.plants.append(GardenPlant(plant=plant, approximate_quantity="Varias macetas"))
            db.session.commit()


initialize_database()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")