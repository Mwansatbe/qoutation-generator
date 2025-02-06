from flask import Flask, render_template, request, redirect, url_for, make_response
from fpdf import FPDF
import datetime
import sqlite3
import os
import uuid

app = Flask(__name__)

# Database setup (SQLite)
DATABASE = 'myrtle_tech_quotations.db'

def get_db():
    db = sqlite3.connect(DATABASE)
    return db

def create_tables():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            email TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            quotation_code TEXT UNIQUE,
            company_name TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')
    db.commit()
    db.close()

create_tables()  # Create tables if they don't exist

# Generate unique quotation code
def generate_quotation_code():
    return str(uuid.uuid4()).split('-')[0].upper()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        customer_name = request.form['customer_name']
        contact = request.form['contact']
        email = request.form['email']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO customers (name, contact, email) VALUES (?, ?, ?)", (customer_name, contact, email))
        customer_id = cursor.lastrowid
        db.commit()
        db.close()

        return redirect(url_for('create_quotation', customer_id=customer_id))

    return render_template('index.html')

@app.route('/create_quotation/<int:customer_id>', methods=['GET', 'POST'])
def create_quotation(customer_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT name, contact, email FROM customers WHERE id=?", (customer_id,))
    customer = cursor.fetchone()
    db.close()

    if request.method == 'POST':
        company_name = request.form['company_name']
        items = []
        
        # Debug print to see what's coming from the form
        print("Form Data:", request.form)
        
        # Modified item collection logic
        for key in request.form:
            if key.startswith('description'):
                index = key.replace('description', '')
                description = request.form.get(f'description{index}')
                if description:  # Only add item if description exists
                    try:
                        quantity = float(request.form.get(f'quantity{index}', 0))
                        unit_price = float(request.form.get(f'unit_price{index}', 0))
                        items.append({
                            'description': description.strip(),
                            'quantity': quantity,
                            'unit_price': unit_price
                        })
                        print(f"Added item: {description} - Qty: {quantity} - Price: {unit_price}")
                    except ValueError as e:
                        print(f"Error processing item {index}: {e}")
                        continue

        # Debug print to see collected items
        print("Collected Items:", items)

        quotation_code = generate_quotation_code()
        issue_date = datetime.date.today().strftime("%Y-%m-%d")
        expiry_date = (datetime.date.today() + datetime.timedelta(days=14)).strftime("%Y-%m-%d")

        # Store quotation in database
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO quotations 
            (customer_id, quotation_code, company_name, issue_date, expiry_date) 
            VALUES (?, ?, ?, ?, ?)""",
            (customer_id, quotation_code, company_name, issue_date, expiry_date))
        quotation_id = cursor.lastrowid
        db.commit()
        db.close()

        # Generate PDF with the collected items
        if not items:
            print("Warning: No items collected for quotation")
        
        pdf = generate_pdf(customer, company_name, items, quotation_code, issue_date, expiry_date)

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=quotation_{quotation_code}.pdf'
        return response

    return render_template('create_quotation.html', customer=customer)

def generate_pdf(customer, company_name, items, quotation_code, issue_date, expiry_date):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", size=12)  # Bold font for headers

    # Company Header
    pdf.cell(200, 10, txt="MYRTLE TECH QUOTATION", ln=1, align="C")
    pdf.set_font("Arial", size=12)  # Regular font for content
    
    # Customer and Quotation Details
    pdf.cell(200, 10, txt=f"Quotation for: {customer[0]}", ln=1, align="L")
    pdf.cell(200, 10, txt=f"Company: {company_name}", ln=1, align="L")
    pdf.cell(200, 10, txt=f"Quotation Code: {quotation_code}", ln=1, align="L")
    pdf.cell(200, 10, txt=f"Issue Date: {issue_date}", ln=1, align="L")
    pdf.cell(200, 10, txt=f"Expiry Date: {expiry_date}", ln=1, align="L")
    pdf.ln(10)

    # Table Headers
    pdf.set_font("Arial", "B", size=12)
    pdf.cell(90, 10, txt="Description", border=1)
    pdf.cell(30, 10, txt="Quantity", border=1, align="C")
    pdf.cell(35, 10, txt="Unit Price", border=1, align="C")
    pdf.cell(35, 10, txt="Total", border=1, align="C", ln=1)

    # Table Content
    pdf.set_font("Arial", size=12)
    total_with_vat = 0
    for item in items:
        total = float(item['quantity']) * float(item['unit_price'])
        total_with_vat += total
        
        # Format numbers to 2 decimal places
        quantity = "{:.2f}".format(float(item['quantity']))
        unit_price = "{:.2f}".format(float(item['unit_price']))
        total_price = "{:.2f}".format(total)
        
        pdf.cell(90, 10, txt=str(item['description']), border=1)
        pdf.cell(30, 10, txt=quantity, border=1, align="R")
        pdf.cell(35, 10, txt=f"ZMW {unit_price}", border=1, align="R")
        pdf.cell(35, 10, txt=f"ZMW {total_price}", border=1, align="R", ln=1)

    # Calculate VAT (16% inclusive)
    vat_rate = 0.16
    subtotal = total_with_vat / (1 + vat_rate)  # Calculate subtotal by removing VAT
    vat = total_with_vat - subtotal  # Calculate VAT amount

    # Format totals to 2 decimal places
    subtotal_formatted = "{:.2f}".format(subtotal)
    vat_formatted = "{:.2f}".format(vat)
    total_formatted = "{:.2f}".format(total_with_vat)

    # Add Totals
    pdf.ln(10)
    pdf.cell(155, 10, txt="Subtotal (excl. VAT):", align="R")
    pdf.cell(35, 10, txt=f"ZMW {subtotal_formatted}", border=1, align="R", ln=1)
    pdf.cell(155, 10, txt="VAT (15%):", align="R")
    pdf.cell(35, 10, txt=f"ZMW {vat_formatted}", border=1, align="R", ln=1)
    pdf.set_font("Arial", "B", size=12)
    pdf.cell(155, 10, txt="Grand Total (incl. VAT):", align="R")
    pdf.cell(35, 10, txt=f"ZMW {total_formatted}", border=1, align="R", ln=1)

    # Add Terms and Conditions
    pdf.ln(20)
    pdf.set_font("Arial", "B", size=10)
    pdf.cell(0, 10, txt="Terms and Conditions:", ln=1)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, txt="1. This quotation is valid for 14 days from the issue date.\n2. Payment terms: 50% deposit required to commence work.\n3. Balance due upon completion.\n4. All prices are VAT inclusive.")

    return pdf.output(dest='S').encode('latin-1')

if __name__ == '__main__':
    app.run(debug=True)