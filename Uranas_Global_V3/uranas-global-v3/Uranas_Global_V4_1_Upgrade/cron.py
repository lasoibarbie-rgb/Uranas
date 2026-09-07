import app
with app.app.app_context():
    print('Monthly invoices created:', app.generate_monthly_invoices())
