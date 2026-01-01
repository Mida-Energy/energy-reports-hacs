import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import matplotlib.dates as mdates
from pathlib import Path
import glob
import os
import warnings
import json
from typing import Dict, List
import shutil
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

warnings.filterwarnings('ignore')

# Chart style configuration
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

class PDFReportGenerator:
    """Professional PDF report generator."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
    
    def _create_custom_styles(self):
        """Create custom styles for the report."""
        # Create new style names instead of overwriting existing ones
        # Main title
        if 'MainTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='MainTitle',
                parent=self.styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#2c3e50'),
                fontName='Helvetica-Bold'
            ))
        
        # Section title
        if 'SectionTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='SectionTitle',
                parent=self.styles['Heading2'],
                fontSize=16,
                spaceBefore=20,
                spaceAfter=12,
                textColor=colors.HexColor('#2980b9'),
                fontName='Helvetica-Bold',
                borderPadding=5,
                borderColor=colors.HexColor('#3498db'),
                borderWidth=1,
                borderRadius=2,
                backgroundColor=colors.HexColor('#ecf0f1')
            ))
        
        # Subtitle
        if 'SubTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='SubTitle',
                parent=self.styles['Heading3'],
                fontSize=12,
                spaceBefore=10,
                spaceAfter=8,
                textColor=colors.HexColor('#34495e')
            ))
        
        # Highlighted text (custom - doesn't exist in default)
        if 'HighlightText' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='HighlightText',
                parent=self.styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                textColor=colors.HexColor('#e74c3c'),
                backColor=colors.HexColor('#fdf2e9'),
                borderPadding=3,
                borderColor=colors.HexColor('#f5b7b1'),
                borderWidth=1
            ))
        
        # Table header (custom)
        if 'TableHeaderStyle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableHeaderStyle',
                parent=self.styles['Normal'],
                fontSize=9,
                alignment=TA_CENTER,
                textColor=colors.white,
                fontName='Helvetica-Bold'
            ))
        
        # Table text (custom)
        if 'TableTextStyle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableTextStyle',
                parent=self.styles['Normal'],
                fontSize=9,
                alignment=TA_CENTER
            ))
        
        # Cover title
        if 'CoverTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CoverTitle',
                parent=self.styles['Title'],
                fontSize=28,
                spaceAfter=20,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#2c3e50'),
                fontName='Helvetica-Bold'
            ))
        
        # Cover subtitle
        if 'CoverSubtitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CoverSubtitle',
                parent=self.styles['Heading2'],
                fontSize=14,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#7f8c8d')
            ))
        
        # Separator line
        if 'LineStyle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='LineStyle',
                parent=self.styles['Normal'],
                fontSize=1,
                spaceBefore=10,
                spaceAfter=10,
                textColor=colors.grey
            ))
        
        # Footer
        if 'FooterStyle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='FooterStyle',
                parent=self.styles['Normal'],
                fontSize=8,
                spaceBefore=5,
                textColor=colors.grey,
                alignment=TA_CENTER
            ))
    
    def create_daily_pdf(self, analysis: Dict, date: datetime.date, output_path: Path, 
                         plot_paths: List[Path], day_data: pd.DataFrame):
        """Create daily report PDF."""
        pdf_path = output_path / f"report_giornaliero_{date.strftime('%Y%m%d')}.pdf"
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        story = []
        
        # Header
        story.append(Paragraph(f"REPORT GIORNALIERO CONSUMI ENERGIA", self.styles['MainTitle']))
        story.append(Paragraph(f"Data: {date.strftime('%d/%m/%Y')}", self.styles['SubTitle']))
        story.append(Paragraph(f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}", self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Summary card
        story.append(Paragraph("SCHEDA RIASSUNTIVA", self.styles['SectionTitle']))
        
        # Create summary table
        summary_data = [
            ["Metrica", "Valore", "Unità"],
            ["Energia totale", f"{analysis.get('total_energy_kwh', 0):.2f}", "kWh"],
            ["Potenza massima", f"{analysis.get('max_power_w', 0):.1f}", "W"],
            ["Potenza media", f"{analysis.get('avg_power_w', 0):.1f}", "W"],
            ["Tensione media", f"{analysis.get('avg_voltage', 0):.1f}", "V"],
            ["Corrente media", f"{analysis.get('avg_current', 0):.2f}", "A"],
            ["Picchi (>95%)", f"{analysis.get('peak_count', 0)}", "n°"],
            ["Punti dati", f"{analysis.get('data_points', 0)}", "n°"]
        ]
        
        summary_table = Table(summary_data, colWidths=[3*cm, 3*cm, 2*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')])
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Charts section
        story.append(Paragraph("GRAFICI ANALISI", self.styles['SectionTitle']))
        
        # Add charts
        for plot_path in plot_paths:
            if plot_path.exists():
                story.append(Paragraph(f"Grafico: {plot_path.stem}", self.styles['SubTitle']))
                try:
                    img = Image(str(plot_path), width=6*inch, height=4*inch)
                    story.append(img)
                    story.append(Spacer(1, 10))
                except Exception as e:
                    story.append(Paragraph(f"Errore nel caricamento del grafico: {str(e)}", self.styles['Normal']))
        
        # Detailed hourly analysis
        story.append(Paragraph("🕒 ANALISI ORARIA DETTAGLIATA", self.styles['SectionTitle']))
        
        if 'hourly_stats' in analysis:
            hourly_data = [["Ora", "Potenza Media (W)", "Max (W)", "Min (W)"]]
            
            hourly_stats = analysis['hourly_stats']
            for hour in range(24):
                mean_val = hourly_stats.get('mean', {}).get(str(hour), 0)
                max_val = hourly_stats.get('max', {}).get(str(hour), 0)
                min_val = hourly_stats.get('min', {}).get(str(hour), 0)
                
                hourly_data.append([
                    f"{hour:02d}:00",
                    f"{mean_val:.1f}",
                    f"{max_val:.1f}",
                    f"{min_val:.1f}"
                ])
            
            # Dividi in due tabelle per evitare overflow
            half = len(hourly_data) // 2
            table1 = Table(hourly_data[:half], colWidths=[2*cm, 3*cm, 2.5*cm, 2.5*cm])
            table2 = Table(hourly_data[half:], colWidths=[2*cm, 3*cm, 2.5*cm, 2.5*cm])
            
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')])
            ])
            
            table1.setStyle(table_style)
            table2.setStyle(table_style)
            
            story.append(table1)
            story.append(Spacer(1, 10))
            story.append(table2)
        
        story.append(Spacer(1, 20))
        
        # Recommendations
        story.append(Paragraph("RACCOMANDAZIONI E SUGGERIMENTI", self.styles['SectionTitle']))
        
        recommendations = []
        if analysis.get('peak_count', 0) > 10:
            recommendations.append("• <b>Ridurre picchi di consumo</b>: identificare i carichi che causano picchi frequenti e distribuirli nel tempo")
        
        if analysis.get('max_power_w', 0) > 3000:
            recommendations.append("• <b>Gestire carichi elevati</b>: valutare la possibilità di spostare carichi > 3kW nelle ore di minor costo")
        
        if analysis.get('total_energy_kwh', 0) > 50:
            recommendations.append("• <b>Ottimizzare consumi</b>: analizzare possibilità di riduzione attraverso interventi di efficienza energetica")
        
        if analysis.get('peak_count', 0) <= 3 and analysis.get('max_power_w', 0) < 2000:
            recommendations.append("• <b>Consumi ottimali</b>: nessuna criticità rilevata, mantenere il buon andamento")
        
        for rec in recommendations:
            story.append(Paragraph(rec, self.styles['Normal']))
            story.append(Spacer(1, 5))
        
        story.append(Spacer(1, 15))
        
        # Footer
        story.append(Paragraph("_" * 80, self.styles['LineStyle']))
        story.append(Spacer(1, 5))
        story.append(Paragraph("Report generato automaticamente da Shelly Energy Analyzer", 
                              self.styles['FooterStyle']))
        
        # Genera PDF
        try:
            doc.build(story)
            print(f"[INFO] PDF created: {pdf_path.name}")
            return pdf_path
        except Exception as e:
            print(f"[ERROR] Error creating PDF: {e}")
            return None
    
    def create_general_pdf(self, analysis: Dict, output_path: Path, plot_paths: List[Path], 
                          all_data: pd.DataFrame, data_files: List[Path]):
        """Create general report PDF - ALWAYS OVERWRITES THE SAME FILE."""
        # Fixed name for general report (overwrites each time)
        pdf_path = output_path / "report_generale.pdf"
        
        # If a file with this name already exists, remove it
        if pdf_path.exists():
            try:
                pdf_path.unlink()
                print(f"[INFO] Removed previous version of general report")
            except Exception as e:
                print(f"[WARN] Could not remove previous file: {e}")
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        story = []
        
        # Cover page
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph("REPORT GENERALE ANALISI CONSUMI", 
                              self.styles['CoverTitle']))
        story.append(Spacer(1, 10))
        story.append(Paragraph("Storico Completo Dati Energetici", 
                              self.styles['CoverSubtitle']))
        story.append(Spacer(1, 20))
        story.append(Paragraph(f"Periodo: {analysis.get('date_range', {}).get('start', 'N/A')} - "
                             f"{analysis.get('date_range', {}).get('end', 'N/A')}", self.styles['Normal']))
        story.append(Paragraph(f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", self.styles['Normal']))
        story.append(Paragraph(f"Ultimo aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 
                              self.styles['HighlightText']))
        story.append(Spacer(1, 40))
        story.append(Paragraph("Shelly Energy Analyzer", 
                              self.styles['FooterStyle']))
        story.append(PageBreak())
        
        # Table of contents
        story.append(Paragraph("📑 INDICE DEL REPORT", self.styles['SectionTitle']))
        story.append(Spacer(1, 10))
        
        toc = [
            "1. SINTESI GENERALE E METRICHE PRINCIPALI",
            "2. ANALISI DETTAGLIATA PER GIORNO",
            "3. GRAFICI DI SINTESI",
            "4. RACCOMANDAZIONI E PIANO DI AZIONE",
            "5. APPENDICE TECNICA"
        ]
        
        for item in toc:
            story.append(Paragraph(f"• {item}", self.styles['Normal']))
            story.append(Spacer(1, 5))
        
        story.append(PageBreak())
        
        # 1. General summary
        story.append(Paragraph("1. SINTESI GENERALE E METRICHE PRINCIPALI", self.styles['SectionTitle']))
        story.append(Spacer(1, 10))
        
        # Main metrics table
        metrics_data = [
            ["METRICA", "VALORE", "NOTE"],
            ["Energia totale", f"{analysis.get('total_energy_kwh', 0):.2f} kWh", "Consumo complessivo"],
            ["Potenza massima", f"{analysis.get('max_power_w', 0):.1f} W", "Picco assoluto rilevato"],
            ["Potenza media", f"{analysis.get('avg_power_w', 0):.1f} W", "Valore medio giornaliero"],
            ["Giorni analizzati", f"{analysis.get('days_analyzed', 0)}", "Periodo di monitoraggio"],
            ["Dati totali", f"{analysis.get('total_data_points', 0):,}", "Punti di misurazione"],
            ["File elaborati", f"{len(data_files)}", "File CSV processati"]
        ]
        
        metrics_table = Table(metrics_data, colWidths=[4*cm, 3*cm, 6*cm])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')])
        ]))
        
        story.append(metrics_table)
        story.append(Spacer(1, 20))
        
        # Daily statistics
        if 'daily_energy_stats' in analysis:
            story.append(Paragraph("Statistiche Giornaliere", self.styles['SubTitle']))
            
            daily_stats = analysis['daily_energy_stats']
            daily_data = [
                ["Statistica", "Valore (kWh)", "Descrizione"],
                ["Consumo massimo", f"{daily_stats.get('max', 0):.2f}", "Giorno con consumo più alto"],
                ["Consumo minimo", f"{daily_stats.get('min', 0):.2f}", "Giorno con consumo più basso"],
                ["Consumo medio", f"{daily_stats.get('avg', 0):.2f}", "Media giornaliera"],
                ["Variazione", f"±{daily_stats.get('max', 0) - daily_stats.get('min', 0):.2f}", "Range di consumo"]
            ]
            
            daily_table = Table(daily_data, colWidths=[4*cm, 3*cm, 6*cm])
            daily_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f8ff')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            
            story.append(daily_table)
        
        story.append(PageBreak())
        
        # 2. Daily analysis
        story.append(Paragraph("2. ANALISI DETTAGLIATA PER GIORNO", self.styles['SectionTitle']))
        
        if 'date' in all_data.columns:
            # Raggruppa dati per giorno
            daily_summary = all_data.groupby('date').agg({
                'total_act_energy': 'sum',
                'max_act_power': ['max', 'mean'],
                'avg_voltage': 'mean',
                'avg_current': 'mean'
            }).round(2)
            
            daily_summary.columns = ['energia_kwh', 'potenza_max', 'potenza_media', 'tensione_media', 'corrente_media']
            daily_summary['energia_kwh'] = daily_summary['energia_kwh'] / 1000
            
            # Create daily summary table
            story.append(Paragraph("Riepilogo Consumi Giornalieri", self.styles['SubTitle']))
            
            table_data = [["Data", "Energia (kWh)", "P.Max (W)", "P.Media (W)", "Tensione (V)"]]
            
            for date_idx, row in daily_summary.iterrows():
                table_data.append([
                    date_idx.strftime('%d/%m'),
                    f"{row['energia_kwh']:.2f}",
                    f"{row['potenza_max']:.0f}",
                    f"{row['potenza_media']:.0f}",
                    f"{row['tensione_media']:.1f}"
                ])
            
            # Dividi in pagine se necessario
            rows_per_page = 20
            for i in range(0, len(table_data), rows_per_page):
                if i > 0:
                    story.append(PageBreak())
                    story.append(Paragraph(f"2. ANALISI DETTAGLIATA PER GIORNO (continua)", self.styles['SectionTitle']))
                
                page_data = table_data[i:i+rows_per_page]
                if i > 0:
                    page_data = [table_data[0]] + page_data
                
                daily_table = Table(page_data, colWidths=[2.5*cm, 3*cm, 2.5*cm, 2.5*cm, 2.5*cm])
                daily_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')])
                ]))
                
                story.append(daily_table)
                story.append(Spacer(1, 10))
        
        story.append(PageBreak())
        
        # 3. Summary charts
        story.append(Paragraph("3. GRAFICI DI SINTESI", self.styles['SectionTitle']))
        
        # Add charts
        for plot_path in plot_paths:
            if plot_path.exists():
                story.append(Paragraph(plot_path.stem.replace('_', ' ').title(), self.styles['SubTitle']))
                try:
                    img = Image(str(plot_path), width=6*inch, height=4*inch)
                    story.append(img)
                    story.append(Spacer(1, 10))
                except Exception as e:
                    story.append(Paragraph(f"Grafico non disponibile: {e}", self.styles['Normal']))
        
        story.append(PageBreak())
        
        # 4. Recommendations and action plan
        story.append(Paragraph("4. RACCOMANDAZIONI E PIANO DI AZIONE", self.styles['SectionTitle']))
        
        # Trend analysis
        story.append(Paragraph("Analisi dei Trend", self.styles['SubTitle']))
        
        trend_analysis = [
            "• <b>Monitoraggio continuo</b>: Implementare sistema di monitoraggio in tempo reale",
            "• <b>Identificazione pattern</b>: Analizzare ricorrenze settimanali e mensili",
            "• <b>Ottimizzazione oraria</b>: Spostare carichi non critici nelle ore di minor costo",
            "• <b>Gestione picchi</b>: Implementare strategie di load shedding",
            "• <b>Manutenzione preventiva</b>: Monitorare efficienza degli impianti"
        ]
        
        for item in trend_analysis:
            story.append(Paragraph(item, self.styles['Normal']))
            story.append(Spacer(1, 3))
        
        story.append(Spacer(1, 15))
        
        # Action plan
        story.append(Paragraph("Piano di Azione Raccomandato", self.styles['SubTitle']))
        
        action_plan = [
            ["Fase", "Attività", "Timeline", "Responsabile"],
            ["1", "Analisi approfondita carichi", "2 settimane", "Team Energia"],
            ["2", "Identificazione ottimizzazioni", "1 settimana", "Team Energia"],
            ["3", "Pianificazione interventi", "1 mese", "Management"],
            ["4", "Implementazione", "2-3 mesi", "Team Tecnico"],
            ["5", "Monitoraggio risultati", "Continuo", "Team Energia"]
        ]
        
        action_table = Table(action_plan, colWidths=[1.5*cm, 6*cm, 3*cm, 3*cm])
        action_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8f6f3')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')])
        ]))
        
        story.append(action_table)
        story.append(Spacer(1, 20))
        
        # Savings estimate
        story.append(Paragraph("Stima Risparmi Potenziali", self.styles['SubTitle']))
        
        savings_text = """
        <b>• Riduzione picchi del 20%</b>: Risparmio sui costi di potenza contrattuale<br/>
        <b>• Ottimizzazione oraria</b>: -10/15% su costo energia tramite tariffe biorarie<br/>
        <b>• Miglioramento efficienza</b>: -5/10% su consumi base<br/>
        <b>• ROI stimato</b>: 12-18 mesi per interventi di media entità<br/>
        <b>• Risparmio annuo stimato</b>: 15-25% sulla bolletta energetica
        """
        
        story.append(Paragraph(savings_text, self.styles['HighlightText']))
        
        story.append(PageBreak())
        
        # 5. Technical appendix
        story.append(Paragraph("5. APPENDICE TECNICA", self.styles['SectionTitle']))
        
        # Technical information
        story.append(Paragraph("Informazioni Tecniche", self.styles['SubTitle']))
        
        tech_info = [
            ["Parametro", "Valore", "Descrizione"],
            ["Dispositivo", "Shelly EM", "Monitor energia trifase"],
            ["Campionamento", "60 secondi", "Intervallo tra misurazioni"],
            ["Metriche", "15+ parametri", "Tensione, corrente, potenza, energia"],
            ["Risoluzione", "0.1W / 0.001kWh", "Precisione misurazioni"],
            ["Formato dati", "CSV timestamp", "Compatibile con tutti i software"],
            ["Periodo analisi", f"{analysis.get('days_analyzed', 0)} giorni", "Copertura temporale"]
        ]
        
        tech_table = Table(tech_info, colWidths=[4*cm, 3*cm, 6*cm])
        tech_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7f8c8d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        story.append(tech_table)
        story.append(Spacer(1, 20))
        
        # Final notes
        story.append(Paragraph("Note Finali e Disclaimer", self.styles['SubTitle']))
        
        disclaimer = """
        <b>Disclaimer:</b> Questo report è stato generato automaticamente sulla base dei dati forniti.
        I valori sono indicativi e devono essere verificati da personale tecnico qualificato.
        
        <b>Note:</b> I dati sono stati corretti automaticamente per eventuali discrepanze temporali del dispositivo.
        Le raccomandazioni sono basate su analisi statistica e best practice del settore.
        
        <b>Contatti:</b> Per ulteriori informazioni o analisi personalizzate, contattare il team di analisi energetica.
        """
        
        story.append(Paragraph(disclaimer, self.styles['Normal']))
        
        # Final footer
        story.append(Spacer(1, 20))
        story.append(Paragraph("_" * 80, self.styles['LineStyle']))
        story.append(Spacer(1, 5))
        story.append(Paragraph("© 2024 Shelly Energy Analyzer - Report Generale Completo", 
                              self.styles['FooterStyle']))
        
        # PDF Generation
        try:
            doc.build(story)
            print(f"[INFO] General PDF created/updated: {pdf_path.name}")
            return pdf_path
        except Exception as e:
            print(f"[ERROR] Error creating general PDF: {e}")
            return None


class ShellyEnergyReport:
    def __init__(
        self, 
        data_dir: str = "data",
        output_dir: str = "reports",
        encoding: str = "utf-8",
        correct_timestamps: bool = True
    ):
        """
        Shelly EM data analyzer with PDF reports.
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.encoding = encoding
        self.correct_timestamps = correct_timestamps
        self.data_files = []
        self.all_data = None
        self.pdf_generator = PDFReportGenerator()
        self.selected_entities = self._load_selected_entities()
    
    def _load_selected_entities(self):
        """Load selected entities from selection file if exists."""
        selection_file = Path("/data/selected_entities.json")
        if not selection_file.exists():
            # Try alternative path
            selection_file = self.data_dir.parent / "selected_entities.json"
        
        if selection_file.exists():
            try:
                with open(selection_file, 'r') as f:
                    data = json.load(f)
                    entities = data.get('entity_ids', [])
                    if entities:
                        print(f"[INFO] Loaded {len(entities)} selected entities from {selection_file}")
                        return entities
            except Exception as e:
                print(f"[WARN] Could not load selected entities: {e}")
        
        return None
        
    def _find_data_files(self):
        """Find all CSV files in the data folder."""
        csv_files = list(self.data_dir.glob("*.csv"))
        csv_files.extend(list(self.data_dir.glob("emdata_*.csv")))
        
        if not csv_files:
            raise FileNotFoundError(f"Nessun file CSV trovato in {self.data_dir}")
        
        self.data_files = sorted(csv_files)
        print(f"[INFO] Found {len(self.data_files)} CSV files:")
        for f in self.data_files:
            print(f"  - {f.name}")
        
        return self.data_files
    
    def _load_and_correct_csv(self, file_path: Path) -> pd.DataFrame:
        """Load and correct a CSV file."""
        print(f"[INFO] Loading: {file_path.name}")
        
        try:
            df = pd.read_csv(file_path, encoding=self.encoding)
        except UnicodeDecodeError:
            for enc in ['latin-1', 'iso-8859-1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, encoding=enc)
                    self.encoding = enc
                    print(f"    - Encoding detected: {enc}")
                    break
                except:
                    continue
            else:
                raise ValueError(f"Impossibile leggere il file {file_path.name}")
        
        df['source_file'] = file_path.name
        
        if 'timestamp' not in df.columns:
            print(f"    [WARN] No 'timestamp' column found")
            df['timestamp'] = int(datetime.now().timestamp()) + df.index * 60
        
        return df
    
    def _correct_timestamps_in_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Correct erroneous timestamps."""
        if not self.correct_timestamps or 'timestamp' not in df.columns:
            return df
        
        df['datetime_raw'] = pd.to_datetime(df['timestamp'], unit='s')
        latest_timestamp_raw = df['datetime_raw'].max()
        current_time = datetime.now()
        time_diff = current_time - latest_timestamp_raw
        
        if abs(time_diff.days) > 30:
            print(f"    [INFO] Timestamp correction: {abs(time_diff.days)} days difference")
            correction_seconds = time_diff.total_seconds()
            df['timestamp_corrected'] = df['timestamp'] + correction_seconds
            df['datetime'] = pd.to_datetime(df['timestamp_corrected'], unit='s')
        else:
            df['datetime'] = df['datetime_raw']
        
        return df
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare the DataFrame with additional metrics."""
        if df is None or len(df) == 0:
            return df
        
        if 'datetime' not in df.columns and 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        elif 'datetime' not in df.columns:
            start_time = datetime.now() - timedelta(hours=len(df)/60)
            df['datetime'] = pd.date_range(start=start_time, periods=len(df), freq='1min')
        
        df['date'] = df['datetime'].dt.date
        df['hour'] = df['datetime'].dt.hour
        df['day'] = df['datetime'].dt.day
        df['month'] = df['datetime'].dt.month
        df['year'] = df['datetime'].dt.year
        df['weekday'] = df['datetime'].dt.weekday
        
        if 'total_act_energy' in df.columns:
            df['energy_kwh'] = df['total_act_energy'] / 1000
        
        if all(col in df.columns for col in ['total_act_energy', 'lag_react_energy']):
            df['power_factor_est'] = df['total_act_energy'] / np.sqrt(
                df['total_act_energy']**2 + df['lag_react_energy']**2 + 1e-6
            )
        
        return df
    
    def load_all_data(self) -> pd.DataFrame:
        """Load and combine all data."""
        print("\n[INFO] Loading and combining all data...")
        
        self._find_data_files()
        
        all_dfs = []
        for file_path in self.data_files:
            try:
                df = self._load_and_correct_csv(file_path)
                df = self._correct_timestamps_in_data(df)
                df = self._prepare_dataframe(df)
                all_dfs.append(df)
                print(f"[INFO] {file_path.name}: {len(df)} rows")
            except Exception as e:
                print(f"[ERROR] Error in {file_path.name}: {e}")
                continue
        
        if not all_dfs:
            raise ValueError("No valid data found")
        
        self.all_data = pd.concat(all_dfs, ignore_index=True, sort=False)
        
        if 'datetime' in self.all_data.columns:
            self.all_data = self.all_data.sort_values('datetime')
        
        print(f"\n[INFO] Combined data: {len(self.all_data)} total rows")
        if 'datetime' in self.all_data.columns:
            print(f"[INFO] Period: {self.all_data['datetime'].min()} - {self.all_data['datetime'].max()}")
            print(f"[INFO] Unique days: {self.all_data['date'].nunique()}")
        
        return self.all_data
    
    def _create_output_structure(self):
        """Create the output folder structure."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.daily_reports_dir = self.output_dir / "giornalieri"
        self.general_report_dir = self.output_dir / "generale"
        
        self.daily_reports_dir.mkdir(exist_ok=True)
        self.general_report_dir.mkdir(exist_ok=True)
        
        print(f"\n[INFO] Output structure created:")
        print(f"  - Daily reports: {self.daily_reports_dir}")
        print(f"  - General report: {self.general_report_dir}")
    
    def _analyze_daily_data(self, date: datetime.date) -> Dict:
        """Analyze data for a single day."""
        day_data = self.all_data[self.all_data['date'] == date]
        
        if len(day_data) == 0:
            return {}
        
        analysis = {
            'date': date.strftime('%Y-%m-%d'),
            'total_energy_kwh': day_data['total_act_energy'].sum() / 1000 if 'total_act_energy' in day_data.columns else 0,
            'avg_power_w': day_data['max_act_power'].mean() if 'max_act_power' in day_data.columns else 0,
            'max_power_w': day_data['max_act_power'].max() if 'max_act_power' in day_data.columns else 0,
            'min_power_w': day_data['min_act_power'].min() if 'min_act_power' in day_data.columns else 0,
            'avg_voltage': day_data['avg_voltage'].mean() if 'avg_voltage' in day_data.columns else 0,
            'avg_current': day_data['avg_current'].mean() if 'avg_current' in day_data.columns else 0,
            'data_points': len(day_data)
        }
        
        if 'max_act_power' in day_data.columns:
            peak_threshold = day_data['max_act_power'].quantile(0.95)
            peaks = day_data[day_data['max_act_power'] > peak_threshold]
            analysis['peak_count'] = len(peaks)
            analysis['peak_threshold_w'] = peak_threshold
        
        if 'hour' in day_data.columns and 'max_act_power' in day_data.columns:
            hourly_stats = day_data.groupby('hour')['max_act_power'].agg(['mean', 'max', 'min']).round(1)
            analysis['hourly_stats'] = hourly_stats.to_dict()
        
        return analysis
    
    def _create_daily_plots(self, day_data: pd.DataFrame, date: datetime.date, output_dir: Path) -> List[Path]:
        """Create charts for a single day and return the paths."""
        plot_paths = []
        
        if len(day_data) == 0:
            return plot_paths
        
        # 1. Power trend
        fig1, ax1 = plt.subplots(figsize=(12, 6))
        if 'datetime' in day_data.columns and 'max_act_power' in day_data.columns:
            ax1.plot(day_data['datetime'], day_data['max_act_power'], 'b-', linewidth=1.5, alpha=0.8)
            ax1.set_title(f'Andamento Potenza - {date.strftime("%d/%m/%Y")}', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Ora del Giorno', fontsize=12)
            ax1.set_ylabel('Potenza (W)', fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.tight_layout()
            plot_path = output_dir / f"potenza_{date.strftime('%Y%m%d')}.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plot_paths.append(plot_path)
            plt.close()
        
        # 2. Hourly profile
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        if 'hour' in day_data.columns and 'max_act_power' in day_data.columns:
            hourly_avg = day_data.groupby('hour')['max_act_power'].mean()
            ax2.bar(hourly_avg.index, hourly_avg.values, alpha=0.7, color='steelblue')
            ax2.set_title(f'Profilo Orario Consumi - {date.strftime("%d/%m/%Y")}', fontsize=14)
            ax2.set_xlabel('Ora del Giorno', fontsize=12)
            ax2.set_ylabel('Potenza Media (W)', fontsize=12)
            ax2.set_xticks(range(0, 24, 2))
            ax2.grid(True, alpha=0.3, axis='y')
            plt.tight_layout()
            plot_path = output_dir / f"profilo_orario_{date.strftime('%Y%m%d')}.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plot_paths.append(plot_path)
            plt.close()
        
        # 3. Power distribution
        fig3, ax3 = plt.subplots(figsize=(10, 6))
        if 'max_act_power' in day_data.columns:
            ax3.hist(day_data['max_act_power'], bins=30, edgecolor='black', alpha=0.7, color='steelblue')
            mean_power = day_data['max_act_power'].mean()
            ax3.axvline(mean_power, color='red', linestyle='--', label=f'Media: {mean_power:.1f} W')
            ax3.set_title(f'Distribuzione Potenza - {date.strftime("%d/%m/%Y")}', fontsize=14)
            ax3.set_xlabel('Potenza (W)', fontsize=12)
            ax3.set_ylabel('Frequenza', fontsize=12)
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            plt.tight_layout()
            plot_path = output_dir / f"distribuzione_{date.strftime('%Y%m%d')}.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plot_paths.append(plot_path)
            plt.close()
        
        return plot_paths
    
    def _create_daily_report(self, date: datetime.date, analysis: Dict, day_data: pd.DataFrame):
        """Create complete report for a single day."""
        date_dir = self.daily_reports_dir / date.strftime("%Y-%m-%d")
        date_dir.mkdir(exist_ok=True)
        
        grafici_dir = date_dir / "grafici"
        dati_dir = date_dir / "dati"
        grafici_dir.mkdir(exist_ok=True)
        dati_dir.mkdir(exist_ok=True)
        
        print(f"[INFO] Creating report for {date.strftime('%d/%m/%Y')}...")
        
        # Save data
        day_data.to_csv(dati_dir / "dati_giornalieri.csv", index=False)
        
        # Create charts
        plot_paths = self._create_daily_plots(day_data, date, grafici_dir)
        
        # Save JSON statistics
        with open(dati_dir / "statistiche.json", 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        # Create PDF
        pdf_path = self.pdf_generator.create_daily_pdf(analysis, date, date_dir, plot_paths, day_data)
        
        if pdf_path:
            # Also create a text version for reference
            with open(date_dir / "riepilogo.txt", 'w', encoding='utf-8') as f:
                f.write(f"Report Giornaliero - {date.strftime('%d/%m/%Y')}\n")
                f.write(f"Energia totale: {analysis.get('total_energy_kwh', 0):.2f} kWh\n")
                f.write(f"Potenza massima: {analysis.get('max_power_w', 0):.1f} W\n")
                f.write(f"PDF disponibile: {pdf_path.name}\n")
            
            print(f"[INFO] PDF report created: {pdf_path.name}")
        else:
            print(f"[WARN] PDF report not created for {date.strftime('%d/%m/%Y')}")
    
    def _create_general_plots(self, plots_dir: Path) -> List[Path]:
        """Create charts for the general report."""
        plot_paths = []
        
        # 1. Daily energy
        if 'date' in self.all_data.columns and 'total_act_energy' in self.all_data.columns:
            fig1, ax1 = plt.subplots(figsize=(14, 7))
            daily_energy = self.all_data.groupby('date')['total_act_energy'].sum() / 1000
            
            ax1.bar(daily_energy.index.astype(str), daily_energy.values, alpha=0.7, color='steelblue')
            ax1.set_title('Energia Consumata per Giorno', fontsize=16, fontweight='bold')
            ax1.set_xlabel('Data', fontsize=12)
            ax1.set_ylabel('Energia (kWh)', fontsize=12)
            ax1.tick_params(axis='x', rotation=45)
            ax1.grid(True, alpha=0.3, axis='y')
            plt.tight_layout()
            plot_path = plots_dir / "energia_giornaliera.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plot_paths.append(plot_path)
            plt.close()
        
        # 2. Consumption heatmap
        if all(col in self.all_data.columns for col in ['date', 'hour', 'max_act_power']):
            fig2, ax2 = plt.subplots(figsize=(12, 8))
            
            pivot_data = self.all_data.pivot_table(
                values='max_act_power',
                index='hour',
                columns='date',
                aggfunc='mean'
            ).fillna(0)
            
            sns.heatmap(pivot_data, cmap='YlOrRd', ax=ax2, cbar_kws={'label': 'Potenza Media (W)'})
            ax2.set_title('Heatmap Consumi Orari - Storico Completo', fontsize=16, fontweight='bold')
            ax2.set_xlabel('Data', fontsize=12)
            ax2.set_ylabel('Ora del Giorno', fontsize=12)
            plt.tight_layout()
            plot_path = plots_dir / "heatmap_consumi.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plot_paths.append(plot_path)
            plt.close()
        
        # 3. Power distribution
        if 'max_act_power' in self.all_data.columns:
            fig3, ax3 = plt.subplots(figsize=(10, 6))
            ax3.hist(self.all_data['max_act_power'], bins=50, edgecolor='black', alpha=0.7, color='steelblue')
            mean_power = self.all_data['max_act_power'].mean()
            ax3.axvline(mean_power, color='red', linestyle='--', label=f'Media: {mean_power:.1f} W')
            ax3.set_title('Distribuzione Potenze - Storico Completo', fontsize=16)
            ax3.set_xlabel('Potenza (W)', fontsize=12)
            ax3.set_ylabel('Frequenza', fontsize=12)
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            plt.tight_layout()
            plot_path = plots_dir / "distribuzione_potenze.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plot_paths.append(plot_path)
            plt.close()
        
        return plot_paths
    
    def _analyze_general_data(self) -> Dict:
        """Analyze all combined data."""
        analysis = {
            'total_energy_kwh': self.all_data['total_act_energy'].sum() / 1000 if 'total_act_energy' in self.all_data.columns else 0,
            'avg_power_w': self.all_data['max_act_power'].mean() if 'max_act_power' in self.all_data.columns else 0,
            'max_power_w': self.all_data['max_act_power'].max() if 'max_act_power' in self.all_data.columns else 0,
            'days_analyzed': self.all_data['date'].nunique() if 'date' in self.all_data.columns else 0,
            'total_data_points': len(self.all_data),
            'date_range': {
                'start': self.all_data['datetime'].min().strftime('%Y-%m-%d') if 'datetime' in self.all_data.columns else 'N/A',
                'end': self.all_data['datetime'].max().strftime('%Y-%m-%d') if 'datetime' in self.all_data.columns else 'N/A'
            }
        }
        
        if 'date' in self.all_data.columns and 'total_act_energy' in self.all_data.columns:
            daily_energy = self.all_data.groupby('date')['total_act_energy'].sum() / 1000
            analysis['daily_energy_stats'] = {
                'max': float(daily_energy.max()),
                'min': float(daily_energy.min()),
                'avg': float(daily_energy.mean()),
                'total_days': len(daily_energy)
            }
            
            max_day = daily_energy.idxmax()
            min_day = daily_energy.idxmin()
            analysis['max_consumption_day'] = {
                'date': max_day.strftime('%Y-%m-%d'),
                'energy_kwh': float(daily_energy.max())
            }
            analysis['min_consumption_day'] = {
                'date': min_day.strftime('%Y-%m-%d'),
                'energy_kwh': float(daily_energy.min())
            }
        
        return analysis
    
    def _create_general_report(self):
        """Create general report - ALWAYS UPDATED."""
        print("\n[INFO] CREATING/UPDATING GENERAL REPORT")
        print("=" * 40)
        
        # Create main folder for general report (without timestamp)
        general_dir = self.general_report_dir
        general_dir.mkdir(exist_ok=True)
        
        grafici_dir = general_dir / "grafici"
        dati_dir = general_dir / "dati"
        grafici_dir.mkdir(exist_ok=True)
        dati_dir.mkdir(exist_ok=True)
        
        # Save complete data
        data_file = dati_dir / "dati_completi.csv"
        self.all_data.to_csv(data_file, index=False)
        print(f"[INFO] Data saved: {data_file.name}")
        
        # Analysis
        general_analysis = self._analyze_general_data()
        
        # Save statistics
        stats_file = dati_dir / "statistiche_generali.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(general_analysis, f, indent=2, default=str)
        print(f"[INFO] Statistics saved: {stats_file.name}")
        
        # Create charts (always overwrite)
        plot_paths = self._create_general_plots(grafici_dir)
        print(f"[INFO] Charts generated: {len(plot_paths)}")
        
        # Create PDF (always overwrite existing file)
        pdf_path = self.pdf_generator.create_general_pdf(
            general_analysis, 
            general_dir, 
            plot_paths, 
            self.all_data, 
            self.data_files
        )
        
        if pdf_path:
            # Update text summary
            with open(general_dir / "riepilogo.txt", 'w', encoding='utf-8') as f:
                f.write(f"REPORT GENERALE - AGGIORNATO AL: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                f.write(f"Periodo: {general_analysis.get('date_range', {}).get('start', 'N/A')} - {general_analysis.get('date_range', {}).get('end', 'N/A')}\n")
                f.write(f"Energia totale: {general_analysis.get('total_energy_kwh', 0):.2f} kWh\n")
                f.write(f"Giorni analizzati: {general_analysis.get('days_analyzed', 0)}\n")
                f.write(f"Dati totali: {general_analysis.get('total_data_points', 0):,} righe\n")
                f.write(f"File CSV processati: {len(self.data_files)}\n")
                f.write(f"PDF principale: {pdf_path.name}\n")
                f.write(f"\nFILE DISPONIBILI:\n")
                f.write(f"- report_generale.pdf (report completo)\n")
                f.write(f"- dati_completi.csv (tutti i dati)\n")
                f.write(f"- statistiche_generali.json (metriche)\n")
                f.write(f"- grafici/ (immagini dei grafici)\n")
            
            print(f"[INFO] General report UPDATED: {pdf_path.name}")
        else:
            print(f"[WARN] General report not created/updated")
        
        return general_dir
    
    def _create_device_report(self, device_id: str, friendly_name: str, device_data: pd.DataFrame):
        """Crea report specifico per un singolo dispositivo."""
        # Sanitize device_id for filename
        safe_device_name = device_id.replace('.', '_').replace('/', '_').replace(':', '_')
        
        # Create device-specific directory
        device_dir = self.general_report_dir / safe_device_name
        device_dir.mkdir(exist_ok=True)
        
        grafici_dir = device_dir / "grafici"
        dati_dir = device_dir / "dati"
        grafici_dir.mkdir(exist_ok=True)
        dati_dir.mkdir(exist_ok=True)
        
        # Save device data
        data_file = dati_dir / f"{safe_device_name}_dati.csv"
        device_data.to_csv(data_file, index=False)
        
        # Analyze device data
        analysis = {
            'device_id': device_id,
            'friendly_name': friendly_name,
            'total_data_points': len(device_data),
            'date_range': {
                'start': device_data['datetime'].min().strftime('%Y-%m-%d %H:%M') if 'datetime' in device_data.columns else 'N/A',
                'end': device_data['datetime'].max().strftime('%Y-%m-%d %H:%M') if 'datetime' in device_data.columns else 'N/A'
            }
        }
        
        if 'total_act_energy' in device_data.columns:
            analysis['total_energy_kwh'] = device_data['total_act_energy'].sum() / 1000
            analysis['avg_power_w'] = device_data['total_act_energy'].mean()
            analysis['max_power_w'] = device_data['total_act_energy'].max()
            analysis['min_power_w'] = device_data['total_act_energy'].min()
        
        if 'max_act_power' in device_data.columns:
            analysis['peak_power_w'] = device_data['max_act_power'].max()
            analysis['avg_power_w'] = device_data['max_act_power'].mean()
        
        # Save statistics
        stats_file = dati_dir / f"{safe_device_name}_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        # Create plots
        plot_paths = self._create_device_plots(device_data, grafici_dir, safe_device_name)
        
        # Create PDF
        pdf_path = device_dir / f"report_{safe_device_name}.pdf"
        self._create_device_pdf(analysis, pdf_path, plot_paths, device_data)
        
        print(f"[INFO] Device report created: {pdf_path.name}")
    
    def _create_device_plots(self, device_data: pd.DataFrame, output_dir: Path, device_name: str) -> List[Path]:
        """Create graphs for every device."""
        plot_paths = []
        
        if len(device_data) == 0:
            return plot_paths
        
        # 1. Power trend over time
        if 'datetime' in device_data.columns and 'max_act_power' in device_data.columns:
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(device_data['datetime'], device_data['max_act_power'], 'b-', linewidth=1.5, alpha=0.8)
            ax.set_title(f'Andamento Potenza nel Tempo', fontsize=14, fontweight='bold')
            ax.set_xlabel('Data/Ora', fontsize=12)
            ax.set_ylabel('Potenza (W)', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
            plt.xticks(rotation=45)
            plt.tight_layout()
            plot_path = output_dir / f"{device_name}_power_trend.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plot_paths.append(plot_path)
            plt.close()
        
        # 2. Daily energy consumption
        if 'date' in device_data.columns and 'total_act_energy' in device_data.columns:
            daily_energy = device_data.groupby('date')['total_act_energy'].sum() / 1000  # kWh
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.bar(range(len(daily_energy)), daily_energy.values, alpha=0.7, color='steelblue')
            ax.set_title(f'Consumo Energetico Giornaliero', fontsize=14, fontweight='bold')
            ax.set_xlabel('Giorno', fontsize=12)
            ax.set_ylabel('Energia (kWh)', fontsize=12)
            ax.set_xticks(range(len(daily_energy)))
            ax.set_xticklabels([d.strftime('%d/%m') for d in daily_energy.index], rotation=45)
            ax.grid(True, alpha=0.3, axis='y')
            plt.tight_layout()
            plot_path = output_dir / f"{device_name}_daily_energy.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plot_paths.append(plot_path)
            plt.close()
        
        # 3. Hourly profile
        if 'hour' in device_data.columns and 'max_act_power' in device_data.columns:
            hourly_avg = device_data.groupby('hour')['max_act_power'].mean()
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.bar(hourly_avg.index, hourly_avg.values, alpha=0.7, color='steelblue')
            ax.set_title(f'Profilo Orario Medio', fontsize=14, fontweight='bold')
            ax.set_xlabel('Ora del Giorno', fontsize=12)
            ax.set_ylabel('Potenza Media (W)', fontsize=12)
            ax.set_xticks(range(0, 24, 2))
            ax.grid(True, alpha=0.3, axis='y')
            plt.tight_layout()
            plot_path = output_dir / f"{device_name}_hourly_profile.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plot_paths.append(plot_path)
            plt.close()
        
        return plot_paths
    
    def _create_device_pdf(self, analysis: Dict, pdf_path: Path, plot_paths: List[Path], device_data: pd.DataFrame):
        """Create PDF per device using the existing generator."""
        try:
            # Use the existing PDF generator with device-specific data
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            story = []
            
            # Title
            story.append(Paragraph(f"REPORT DISPOSITIVO", self.pdf_generator.styles['MainTitle']))
            story.append(Paragraph(f"{analysis['friendly_name']}", self.pdf_generator.styles['SubTitle']))
            story.append(Paragraph(f"Entity ID: {analysis['device_id']}", self.pdf_generator.styles['Normal']))
            story.append(Paragraph(f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}", self.pdf_generator.styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Summary
            story.append(Paragraph("RIEPILOGO", self.pdf_generator.styles['SectionTitle']))
            
            summary_data = [
                ["Metrica", "Valore", "Unità"],
                ["Periodo", f"{analysis['date_range']['start']} - {analysis['date_range']['end']}", ""],
                ["Energia totale", f"{analysis.get('total_energy_kwh', 0):.2f}", "kWh"],
                ["Potenza media", f"{analysis.get('avg_power_w', 0):.1f}", "W"],
                ["Potenza massima", f"{analysis.get('peak_power_w', 0):.1f}", "W"],
                ["Punti dati", f"{analysis['total_data_points']}", "n°"]
            ]
            
            summary_table = Table(summary_data, colWidths=[5*cm, 4*cm, 2*cm])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Plots
            story.append(Paragraph("GRAFICI", self.pdf_generator.styles['SectionTitle']))
            for plot_path in plot_paths:
                if plot_path.exists():
                    img = Image(str(plot_path), width=15*cm, height=9*cm)
                    story.append(img)
                    story.append(Spacer(1, 10))
            
            doc.build(story)
            print(f"[INFO] PDF saved: {pdf_path.name}")
            
        except Exception as e:
            print(f"[ERROR] Error creating PDF: {e}")
    
    def run_analysis(self):
        """Execute complete analysis with separate reports per device."""
        print("=" * 60)
        print("SHELLY EM CONSUMPTION ANALYZER - PDF REPORT PER DEVICE")
        print("=" * 60)
        
        if not self.data_dir.exists():
            print(f"[ERROR] Data folder not found: {self.data_dir}")
            print(f"[INFO] Create 'data' folder and insert CSV files")
            return
        
        self._create_output_structure()
        
        try:
            self.load_all_data()
        except Exception as e:
            print(f"[ERROR] Error loading data: {e}")
            return
        
        # Check if we have entity_id column for per-device analysis
        if 'entity_id' not in self.all_data.columns:
            print("[WARN] entity_id column not found - creating aggregated report")
            self._create_general_report()
            return
        
        # Get unique devices
        unique_devices = self.all_data['entity_id'].unique()
        print(f"[INFO] Total devices in data: {len(unique_devices)}")
        
        # Filter by selected entities if available
        if self.selected_entities:
            print(f"[INFO] Filtering by {len(self.selected_entities)} selected entities")
            unique_devices = [d for d in unique_devices if d in self.selected_entities]
            print(f"[INFO] Devices to process after filtering: {len(unique_devices)}")
            
            if len(unique_devices) == 0:
                print("[WARN] No selected devices found in data. Possible entity_id mismatch.")
                print("[INFO] Available entity_ids in data:")
                for eid in self.all_data['entity_id'].unique():
                    print(f"  - {eid}")
                return
        else:
            print(f"[INFO] No selection filter - processing all {len(unique_devices)} devices")
        
        for device_id in unique_devices:
            device_data = self.all_data[self.all_data['entity_id'] == device_id].copy()
            friendly_name = device_data['friendly_name'].iloc[0] if 'friendly_name' in device_data.columns and len(device_data) > 0 else device_id
            
            print(f"[INFO] Analyzing device: {friendly_name}")
            print(f"  - Entity ID: {device_id}")
            print(f"  - Data: {len(device_data)} rows")
            
            # Create device-specific report
            self._create_device_report(device_id, friendly_name, device_data)
        
        print(f"[INFO] Analysis completed for {len(unique_devices)} devices")
        
        # Final summary
        print("=" * 60)
        print("ANALYSIS COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("GENERATED OUTPUT SUMMARY:")
        print(f"  - CSV files processed: {len(self.data_files)}")
        print(f"  - Reports generated: {len(unique_devices)}")
        if self.selected_entities:
            print(f"  - Selected entities: {len(self.selected_entities)}")
        print(f"  - Total data analyzed: {len(self.all_data):,} rows")
        print("MAIN PATHS:")
        print(f"  - Daily reports: {self.daily_reports_dir}")
        print(f"  - General report: {self.general_report_dir}")
        print(f"  - Output files: {self.general_report_dir}")
        print("=" * 60)


def main():
    print("=" * 60)
    print("SHELLY ENERGY ANALYZER - PROFESSIONAL PDF REPORTS")
    print("=" * 60)
    
    print("\n[INFO] This program generates professional PDF reports:")
    print("  1. Daily reports in reports/giornalieri/")
    print("  2. General report ALWAYS UPDATED in reports/generale/")
    print("  3. Everything in PDF format with embedded charts")
    print("  4. Automatic timestamp correction")
    print("  5. General report overwritten on each execution")
    print("=" * 60)
    
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"\n[WARN] 'data' folder not found.")
        create_folder = input("   Do you want to create the 'data' folder? (y/n): ").lower()
        if create_folder == 'y':
            data_dir.mkdir(exist_ok=True)
            print(f"[INFO] 'data' folder created.")
            print(f"[INFO] Insert CSV files in the 'data/' folder and run the program again.")
            return
        else:
            return
    
    try:
        analyzer = ShellyEnergyReport(
            data_dir="data",
            output_dir="reports",
            correct_timestamps=True
        )
        
        analyzer.run_analysis()
        
    except Exception as e:
        print(f"\n[ERROR] Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Check dependencies
    try:
        from reportlab.lib.pagesizes import A4
        print("[INFO] All dependencies are correctly installed.")
    except ImportError:
        print("\n[ERROR] REPORTLAB not installed!")
        print("[INFO] Install with: pip install reportlab")
        exit(1)
    
    main()