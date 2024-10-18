from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
import os
import json

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
    qr_code_path = db.Column(db.String(200), nullable=True)

# Define the User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # Either 'farmer' or 'distributor'
    password_hash = db.Column(db.String(200), nullable=False)

# Create the database tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')
@app.route('/product/<int:product_id>')
def show_qr_code(product_id):
    # Get the product by its ID
    product = Product.query.get(product_id)
    if not product:
        return "Product not found", 404
    
    # Render the template to show the QR code
    return render_template('show_qr_code.html', product=product)
# Sign-up page where user can choose to be a farmer or distributor
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role = request.form['role']
        username = request.form['username']
        city = request.form['city']
        state = request.form['state']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        # Create a new user and save to the database
        new_user = User(username=username, city=city, state=state, role=role, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('index'))
    return render_template('signup.html')

# Login page for farmers and distributors
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
        else:
            return "Invalid credentials or role"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Add product for farmers
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'role' in session and session['role'] == 'farmer':
        if request.method == 'POST':
            name = request.form['name']
            quantity = int(request.form['quantity'])
            price = int(request.form['price'])

            # Create a new product entry in the database
            new_product = Product(name=name, quantity=quantity, price=price)

            # Generate the QR code for the product details
            qr_data = {
                'name': name,
                'quantity': quantity,
                'price': price
            }
            
            # Create a QR code with the product details
            qr = qrcode.QRCode()
            qr.add_data(json.dumps(qr_data))  # Convert dict to JSON string
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')

            # Save QR code image
            qr_code_filename = f"static/qr_codes/{name}_qr.png"
            if not os.path.exists('static/qr_codes'):
                os.makedirs('static/qr_codes')
            img.save(qr_code_filename)

            # Save the QR code file path in the product model
            new_product.qr_code_path = qr_code_filename

            # Add the product to the database
            db.session.add(new_product)
            db.session.commit()

            return redirect(url_for('view_products'))
        
        return render_template('add_product.html')
    return redirect(url_for('login'))

# View products for distributors
@app.route('/view_products')
def view_products():
    if 'role' in session and session['role'] == 'distributor':
        products = Product.query.all()
        return render_template('product_list.html', products=products)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
