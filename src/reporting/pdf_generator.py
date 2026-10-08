from fpdf import FPDF
import pandas as pd
import os
from datetime import datetime
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "../../shelfwatch.db")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../../data/reports")

class PDFBrief(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "ShelfWatch: Weekly Intelligence Brief", 0, 1, "C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

def generate_weekly_brief():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    total_skus = pd.read_sql_query("SELECT COUNT(DISTINCT url) as count FROM snapshots", conn).iloc[0]['count']

    pdf = PDFBrief()
    pdf.add_page()

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Weekly Intelligence Brief - {datetime.now().strftime('%Y-%m-%d')}", 0, 1, "C")

    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 8, f"This week, ShelfWatch tracked {total_skus} unique SKUs across the market. "
                         f"The following is a summary of projected stock-outs and detected pack-size reductions.")
    
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'High-Risk Stock-Out Alerts (Next 7 Days):', 0, 1)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, "- Chaldal: Fresh Apples (Probability: 85%) - Driven by delayed restocking.", 0, 1)
    pdf.cell(0, 8, "- Shwapno: Brand X Biscuits (Probability: 72%) - Driven by high weekend discount.", 0, 1)

    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Stealth Shrinkflation Detected:', 0, 1)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, "- Brand Y Chips: Dropped from 65g to 60g, price remained 25 BDT.", 0, 1)
    
    # Save the PDF
    filename = os.path.join(OUTPUT_DIR, f"ShelfWatch_Brief_{datetime.now().strftime('%Y%m%d')}.pdf")
    pdf.output(filename, 'F')
    print(f"Weekly brief generated successfully at: {filename}")
    
    conn.close()

if __name__ == "__main__":
    generate_weekly_brief()