from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import qrcode
import os

# Flask app setup
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Secret key for session management

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///goods.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db = SQLAlchemy(app)

# Define the Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    farmer_name = db.Column(db.String(80), nullable=False)
    manufacture_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def generate_qr_code(self):
        qr_data = f"Product: {self.name}, Price: {self.price}, Farmer: {self.farmer_name}"
        qr = qrcode.make(qr_data)
        qr_code_path = f'static/qr_codes/{self.id}.png'
        qr.save(qr_code_path)
        return qr_code_path

# Define the User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # Either 'farmer' or 'distributor'
    password_hash = db.Column(db.String(200), nullable=False)

# Define the Order model
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    distributor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='waiting')
    chain = db.Column(db.String(255), nullable=True)

    product = db.relationship('Product', backref='orders', lazy=True)

# Create the database tables
with app.app_context():
    db.create_all()
    os.makedirs('static/qr_codes', exist_ok=True)  # Create directory for QR codes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role = request.form['role']
        username = request.form['username']
        city = request.form['city']
        state = request.form['state']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        new_user = User(username=username, city=city, state=state, role=role, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        user = User.query.filter_by(username=username, role=role).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role

            if role == 'farmer':
                return redirect(url_for('add_product'))
            elif role == 'distributor':
                return redirect(url_for('view_products'))
            elif role == 'consumer':
                return redirect(url_for('view_products_consumer'))
        else:
            return "Invalid credentials or role"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'role' in session and session['role'] == 'farmer':
        if request.method == 'POST':
            name = request.form['name']
            quantity = int(request.form['quantity'])
            price = int(request.form['price'])
            farmer_name = session['username']

            new_product = Product(name=name, quantity=quantity, price=price, farmer_name=farmer_name, farmer_id=session['user_id'])
            db.session.add(new_product)
            db.session.commit()

            # Generate QR code for the new product
            qr_code_path = new_product.generate_qr_code()

            return render_template('add_product.html', qr_code_path=qr_code_path)

        accepted_rejected_orders = Order.query.filter_by(farmer_id=session['user_id']).filter(Order.status.in_(["accepted", "rejected"])).all()
        return render_template('add_product.html', accepted_rejected_orders=accepted_rejected_orders)
    return redirect(url_for('login'))

@app.route('/view_products_consumer')
def view_products_consumer():
    if 'role' in session and session['role'] == 'consumer':
        products = Product.query.all()
        return render_template('product_list_consumer.html', products=products)
    return redirect(url_for('login'))

@app.route('/view_products')
def view_products():
    if 'role' in session and session['role'] == 'distributor':
        products = Product.query.all()
        accepted_orders = Order.query.filter_by(distributor_id=session['user_id'], status='accepted').all()
        accepted_product_ids = [order.product_id for order in accepted_orders]
        
        available_products = [product for product in products if product.id not in accepted_product_ids]
        
        return render_template('product_list.html', products=available_products, accepted_orders=accepted_orders)
    return redirect(url_for('login'))

@app.route('/buy/<int:product_id>', methods=['POST'])
def buy_product(product_id):
    if 'role' in session and session['role'] == 'distributor':
        product = Product.query.get_or_404(product_id)
        existing_order = Order.query.filter_by(product_id=product.id, distributor_id=session['user_id'], status='waiting').first()
        if not existing_order:
            new_order = Order(
                product_id=product.id,
                distributor_id=session['user_id'],
                farmer_id=product.farmer_id,
                status='waiting'
            )
            db.session.add(new_order)
            db.session.commit()

        return redirect(url_for('view_orders_distributor'))
    return redirect(url_for('login'))

@app.route('/distributor/orders')
def view_orders_distributor():
    if 'role' in session and session['role'] == 'distributor':
        orders = Order.query.filter_by(distributor_id=session['user_id']).all()
        return render_template('distributor_orders.html', orders=orders)
    return redirect(url_for('login'))

@app.route('/farmer/orders')
def view_orders_farmer():
    if 'role' in session and session['role'] == 'farmer':
        orders = Order.query.filter_by(farmer_id=session['user_id']).all()
        return render_template('farmer_orders.html', orders=orders)
    return redirect(url_for('login'))

@app.route('/farmer/orders/<int:order_id>/<action>')
def update_order_status(order_id, action):
    if 'role' in session and session['role'] == 'farmer':
        order = Order.query.get_or_404(order_id)
        if action == 'accept':
            order.status = 'accepted'
        elif action == 'reject':
            order.status = 'rejected'
        db.session.commit()
        return redirect(url_for('view_orders_farmer'))
    return redirect(url_for('login'))

@app.route('/confirm_payment/<int:order_id>')
def confirm_payment(order_id):
    if 'role' in session and session['role'] == 'farmer':
        order = Order.query.get_or_404(order_id)
        order.status = 'accepted'
        
        farmer = User.query.get(order.farmer_id)
        distributor = User.query.get(order.distributor_id)
        order.chain = f"{farmer.username} -> {distributor.username}"
        
        db.session.commit()
        return redirect(url_for('view_orders_farmer'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
