from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import qrcode
import os
import json

# Flask app setup
app = Flask(__name__)

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

# Create the database tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_good', methods=['POST'])
def add_good():
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

@app.route('/view_products')
def view_products():
    # Retrieve all products from the database
    products = Product.query.all()

    # Render the products on a new HTML page
    return render_template('product_list.html', products=products)

# Route to display QR code for a specific product
@app.route('/qr_code/<int:product_id>', methods=['GET'])
def view_qr_code(product_id):
    product = Product.query.get(product_id)
    if product:
        # Display the QR code associated with the product
        return render_template('qr_code_display.html', product=product)
    else:
        return "Product not found!", 404

if __name__ == '__main__':
    app.run(debug=True)
