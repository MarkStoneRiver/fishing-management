from flask import Blueprint, render_template, request, redirect, url_for
from db import get_connection

gyoba_bp = Blueprint('gyoba', __name__)


@gyoba_bp.route("/gyoba", methods=["GET", "POST"])
def gyoba():
    company_name = ""
    if request.method == "POST":
        company_name = request.form["company_name"]
        conn = get_connection()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM companies")
        count = c.fetchone()[0]

        if count > 0:
            c.execute("UPDATE companies SET company_name = ?", (company_name,))
        else:
            c.execute("INSERT INTO companies (company_name) VALUES (?)", (company_name,))

        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT company_name FROM companies LIMIT 1")
    result = c.fetchone()
    if result:
        company_name = result[0]
    conn.close()

    return render_template("gyoba.html", company_name=company_name)
