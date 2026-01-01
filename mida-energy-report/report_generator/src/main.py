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

# Configurazione stile grafici
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

class PDFReportGenerator:
    """Generatore di report PDF professionali."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
    
    def _create_custom_styles(self):
        """Crea stili personalizzati per il report."""
        # Crea nuovi nomi di stili invece di sovrascrivere quelli esistenti
        # Titolo principale
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
        
        # Titolo sezione
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
        
        # Sottotitolo
        if 'SubTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='SubTitle',
                parent=self.styles['Heading3'],
                fontSize=12,
                spaceBefore=10,
                spaceAfter=8,
                textColor=colors.HexColor('#34495e')
            ))
        
        # Testo evidenziato (custom - non esiste nel default)
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
        
        # Intestazione tabella (custom)
        if 'TableHeaderStyle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableHeaderStyle',
                parent=self.styles['Normal'],
                fontSize=9,
                alignment=TA_CENTER,
                textColor=colors.white,
                fontName='Helvetica-Bold'
            ))
        
        # Testo tabella (custom)
        if 'TableTextStyle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableTextStyle',
                parent=self.styles['Normal'],
                fontSize=9,
                alignment=TA_CENTER
            ))
        
        # Copertina titolo
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
        
        # Copertina sottotitolo
        if 'CoverSubtitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CoverSubtitle',
                parent=self.styles['Heading2'],
                fontSize=14,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#7f8c8d')
            ))
        
        # Linea separatrice
        if 'LineStyle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='LineStyle',
                parent=self.styles['Normal'],
                fontSize=1,
                spaceBefore=10,
                spaceAfter=10,
                textColor=colors.grey
            ))
        
        # Piè di pagina
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
        """Crea PDF del report giornaliero."""
        pdf_path = output_path / f"report_giornaliero_{date.strftime('%Y%m%d')}.pdf"
        
        # Crea documento PDF
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        story = []
        
        # Intestazione
        story.append(Paragraph(f"REPORT GIORNALIERO CONSUMI ENERGIA", self.styles['MainTitle']))
        story.append(Paragraph(f"Data: {date.strftime('%d/%m/%Y')}", self.styles['SubTitle']))
        story.append(Paragraph(f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}", self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Scheda riassuntiva
        story.append(Paragraph("SCHEDA RIASSUNTIVA", self.styles['SectionTitle']))
        
        # Crea tabella riassuntiva
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
        
        # Sezione grafici
        story.append(Paragraph("GRAFICI ANALISI", self.styles['SectionTitle']))
        
        # Aggiungi grafici
        for plot_path in plot_paths:
            if plot_path.exists():
                story.append(Paragraph(f"Grafico: {plot_path.stem}", self.styles['SubTitle']))
                try:
                    img = Image(str(plot_path), width=6*inch, height=4*inch)
                    story.append(img)
                    story.append(Spacer(1, 10))
                except Exception as e:
                    story.append(Paragraph(f"Errore nel caricamento del grafico: {str(e)}", self.styles['Normal']))
        
        # Analisi oraria dettagliata
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
        
        # Raccomandazioni
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
        
        # Piè di pagina
        story.append(Paragraph("_" * 80, self.styles['LineStyle']))
        story.append(Spacer(1, 5))
        story.append(Paragraph("Report generato automaticamente da Shelly Energy Analyzer", 
                              self.styles['FooterStyle']))
        
        # Genera PDF
        try:
            doc.build(story)
            print(f"    📄 PDF creato: {pdf_path.name}")
            return pdf_path
        except Exception as e:
            print(f"    ❌ Errore nella creazione del PDF: {e}")
            return None
    
    def create_general_pdf(self, analysis: Dict, output_path: Path, plot_paths: List[Path], 
                          all_data: pd.DataFrame, data_files: List[Path]):
        """Crea PDF del report generale - SOVRASCRIVE SEMPRE LO STESSO FILE."""
        # Nome fisso per il report generale (sovrascrive ogni volta)
        pdf_path = output_path / "report_generale.pdf"
        
        # Se esiste già un file con questo nome, lo rimuoviamo
        if pdf_path.exists():
            try:
                pdf_path.unlink()
                print(f"    📄 Rimossa versione precedente del report generale")
            except Exception as e:
                print(f"    ⚠️  Non è stato possibile rimuovere il file precedente: {e}")
        
        # Crea documento PDF
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        story = []
        
        # Copertina
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
        
        # Indice
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
        
        # 1. Sintesi generale
        story.append(Paragraph("1. SINTESI GENERALE E METRICHE PRINCIPALI", self.styles['SectionTitle']))
        story.append(Spacer(1, 10))
        
        # Tabella metriche principali
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
        
        # Statistiche giornaliere
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
        
        # 2. Analisi per giorno
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
            
            # Crea tabella riassuntiva giorni
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
        
        # 3. Grafici di sintesi
        story.append(Paragraph("3. GRAFICI DI SINTESI", self.styles['SectionTitle']))
        
        # Aggiungi grafici
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
        
        # 4. Raccomandazioni e piano di azione
        story.append(Paragraph("4. RACCOMANDAZIONI E PIANO DI AZIONE", self.styles['SectionTitle']))
        
        # Analisi trend
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
        
        # Piano di azione
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
        
        # Stima risparmi
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
        
        # 5. Appendice tecnica
        story.append(Paragraph("5. APPENDICE TECNICA", self.styles['SectionTitle']))
        
        # Informazioni tecniche
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
        
        # Note finali
        story.append(Paragraph("Note Finali e Disclaimer", self.styles['SubTitle']))
        
        disclaimer = """
        <b>Disclaimer:</b> Questo report è stato generato automaticamente sulla base dei dati forniti.
        I valori sono indicativi e devono essere verificati da personale tecnico qualificato.
        
        <b>Note:</b> I dati sono stati corretti automaticamente per eventuali discrepanze temporali del dispositivo.
        Le raccomandazioni sono basate su analisi statistica e best practice del settore.
        
        <b>Contatti:</b> Per ulteriori informazioni o analisi personalizzate, contattare il team di analisi energetica.
        """
        
        story.append(Paragraph(disclaimer, self.styles['Normal']))
        
        # Piè di pagina finale
        story.append(Spacer(1, 20))
        story.append(Paragraph("_" * 80, self.styles['LineStyle']))
        story.append(Spacer(1, 5))
        story.append(Paragraph("© 2024 Shelly Energy Analyzer - Report Generale Completo", 
                              self.styles['FooterStyle']))
        
        # Genera PDF
        try:
            doc.build(story)
            print(f"📄 PDF generale creato/aggiornato: {pdf_path.name}")
            return pdf_path
        except Exception as e:
            print(f"❌ Errore nella creazione del PDF generale: {e}")
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
        Analizzatore dati Shelly EM con report PDF.
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.encoding = encoding
        self.correct_timestamps = correct_timestamps
        self.data_files = []
        self.all_data = None
        self.pdf_generator = PDFReportGenerator()
        
    def _find_data_files(self):
        """Trova tutti i file CSV nella cartella data."""
        csv_files = list(self.data_dir.glob("*.csv"))
        csv_files.extend(list(self.data_dir.glob("emdata_*.csv")))
        
        if not csv_files:
            raise FileNotFoundError(f"Nessun file CSV trovato in {self.data_dir}")
        
        self.data_files = sorted(csv_files)
        print(f"Trovati {len(self.data_files)} file CSV:")
        for f in self.data_files:
            print(f"  - {f.name}")
        
        return self.data_files
    
    def _load_and_correct_csv(self, file_path: Path) -> pd.DataFrame:
        """Carica e corregge un file CSV."""
        print(f"  Caricando: {file_path.name}")
        
        try:
            df = pd.read_csv(file_path, encoding=self.encoding)
        except UnicodeDecodeError:
            for enc in ['latin-1', 'iso-8859-1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, encoding=enc)
                    self.encoding = enc
                    print(f"    - Encoding rilevato: {enc}")
                    break
                except:
                    continue
            else:
                raise ValueError(f"Impossibile leggere il file {file_path.name}")
        
        df['source_file'] = file_path.name
        
        if 'timestamp' not in df.columns:
            print(f"    [WARN] Nessuna colonna 'timestamp' trovata")
            df['timestamp'] = int(datetime.now().timestamp()) + df.index * 60
        
        return df
    
    def _correct_timestamps_in_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Corregge i timestamp errati."""
        if not self.correct_timestamps or 'timestamp' not in df.columns:
            return df
        
        df['datetime_raw'] = pd.to_datetime(df['timestamp'], unit='s')
        latest_timestamp_raw = df['datetime_raw'].max()
        current_time = datetime.now()
        time_diff = current_time - latest_timestamp_raw
        
        if abs(time_diff.days) > 30:
            print(f"    [INFO] Correzione timestamp: {abs(time_diff.days)} giorni di differenza")
            correction_seconds = time_diff.total_seconds()
            df['timestamp_corrected'] = df['timestamp'] + correction_seconds
            df['datetime'] = pd.to_datetime(df['timestamp_corrected'], unit='s')
        else:
            df['datetime'] = df['datetime_raw']
        
        return df
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepara il DataFrame con metriche aggiuntive."""
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
        """Carica e combina tutti i dati."""
        print("\n📚 Caricamento e combinazione di tutti i dati...")
        
        self._find_data_files()
        
        all_dfs = []
        for file_path in self.data_files:
            try:
                df = self._load_and_correct_csv(file_path)
                df = self._correct_timestamps_in_data(df)
                df = self._prepare_dataframe(df)
                all_dfs.append(df)
                print(f"    ✅ {file_path.name}: {len(df)} righe")
            except Exception as e:
                print(f"    ❌ Errore in {file_path.name}: {e}")
                continue
        
        if not all_dfs:
            raise ValueError("Nessun dato valido trovato")
        
        self.all_data = pd.concat(all_dfs, ignore_index=True, sort=False)
        
        if 'datetime' in self.all_data.columns:
            self.all_data = self.all_data.sort_values('datetime')
        
        print(f"\n✅ Dati combinati: {len(self.all_data)} righe totali")
        if 'datetime' in self.all_data.columns:
            print(f"📅 Periodo: {self.all_data['datetime'].min()} - {self.all_data['datetime'].max()}")
            print(f"📆 Giorni unici: {self.all_data['date'].nunique()}")
        
        return self.all_data
    
    def _create_output_structure(self):
        """Crea la struttura delle cartelle di output."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.daily_reports_dir = self.output_dir / "giornalieri"
        self.general_report_dir = self.output_dir / "generale"
        
        self.daily_reports_dir.mkdir(exist_ok=True)
        self.general_report_dir.mkdir(exist_ok=True)
        
        print(f"\n📁 Struttura output creata:")
        print(f"  • Report giornalieri: {self.daily_reports_dir}")
        print(f"  • Report generale: {self.general_report_dir}")
    
    def _analyze_daily_data(self, date: datetime.date) -> Dict:
        """Analizza i dati di un singolo giorno."""
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
        """Crea grafici per un singolo giorno e restituisce i percorsi."""
        plot_paths = []
        
        if len(day_data) == 0:
            return plot_paths
        
        # 1. Andamento potenza
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
        
        # 2. Profilo orario
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
        
        # 3. Distribuzione potenza
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
        """Crea report completo per un singolo giorno."""
        date_dir = self.daily_reports_dir / date.strftime("%Y-%m-%d")
        date_dir.mkdir(exist_ok=True)
        
        grafici_dir = date_dir / "grafici"
        dati_dir = date_dir / "dati"
        grafici_dir.mkdir(exist_ok=True)
        dati_dir.mkdir(exist_ok=True)
        
        print(f"  📊 Creando report per {date.strftime('%d/%m/%Y')}...")
        
        # Salva dati
        day_data.to_csv(dati_dir / "dati_giornalieri.csv", index=False)
        
        # Crea grafici
        plot_paths = self._create_daily_plots(day_data, date, grafici_dir)
        
        # Salva statistiche JSON
        with open(dati_dir / "statistiche.json", 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        # Crea PDF
        pdf_path = self.pdf_generator.create_daily_pdf(analysis, date, date_dir, plot_paths, day_data)
        
        if pdf_path:
            # Crea anche una versione testuale per riferimento
            with open(date_dir / "riepilogo.txt", 'w', encoding='utf-8') as f:
                f.write(f"Report Giornaliero - {date.strftime('%d/%m/%Y')}\n")
                f.write(f"Energia totale: {analysis.get('total_energy_kwh', 0):.2f} kWh\n")
                f.write(f"Potenza massima: {analysis.get('max_power_w', 0):.1f} W\n")
                f.write(f"PDF disponibile: {pdf_path.name}\n")
            
            print(f"    ✅ Report PDF creato: {pdf_path.name}")
        else:
            print(f"    ⚠️  Report PDF non creato per {date.strftime('%d/%m/%Y')}")
    
    def _create_general_plots(self, plots_dir: Path) -> List[Path]:
        """Crea grafici per il report generale."""
        plot_paths = []
        
        # 1. Energia giornaliera
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
        
        # 2. Heatmap consumi
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
        
        # 3. Distribuzione potenze
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
        """Analizza tutti i dati combinati."""
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
        """Crea report generale - SEMPRE AGGIORNATO."""
        print("\n📈 CREAZIONE/AGGIORNAMENTO REPORT GENERALE")
        print("=" * 40)
        
        # Crea cartella principale per il report generale (senza timestamp)
        general_dir = self.general_report_dir
        general_dir.mkdir(exist_ok=True)
        
        grafici_dir = general_dir / "grafici"
        dati_dir = general_dir / "dati"
        grafici_dir.mkdir(exist_ok=True)
        dati_dir.mkdir(exist_ok=True)
        
        # Salva dati completi
        data_file = dati_dir / "dati_completi.csv"
        self.all_data.to_csv(data_file, index=False)
        print(f"  💾 Dati salvati: {data_file.name}")
        
        # Analisi
        general_analysis = self._analyze_general_data()
        
        # Salva statistiche
        stats_file = dati_dir / "statistiche_generali.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(general_analysis, f, indent=2, default=str)
        print(f"  📊 Statistiche salvate: {stats_file.name}")
        
        # Crea grafici (sovrascrive sempre)
        plot_paths = self._create_general_plots(grafici_dir)
        print(f"  📈 Grafici generati: {len(plot_paths)}")
        
        # Crea PDF (sovrascrive sempre il file esistente)
        pdf_path = self.pdf_generator.create_general_pdf(
            general_analysis, 
            general_dir, 
            plot_paths, 
            self.all_data, 
            self.data_files
        )
        
        if pdf_path:
            # Aggiorna riepilogo testuale
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
            
            print(f"✅ Report generale AGGIORNATO: {pdf_path.name}")
        else:
            print(f"⚠️  Report generale non creato/aggiornato")
        
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
        
        print(f"   ✅ Report creato: {pdf_path.name}")
    
    def _create_device_plots(self, device_data: pd.DataFrame, output_dir: Path, device_name: str) -> List[Path]:
        """Crea grafici per un dispositivo."""
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
        """Crea PDF per dispositivo usando il generatore esistente."""
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
            print(f"      PDF salvato: {pdf_path.name}")
            
        except Exception as e:
            print(f"      ❌ Errore creazione PDF: {e}")
    
    def run_analysis(self):
        """Esegue l'analisi completa con report separati per dispositivo."""
        print("=" * 60)
        print("ANALIZZATORE CONSUMI SHELLY EM - REPORT PDF PER DISPOSITIVO")
        print("=" * 60)
        
        if not self.data_dir.exists():
            print(f"❌ Cartella dati non trovata: {self.data_dir}")
            print(f"   Crea la cartella 'data' e inserisci i file CSV")
            return
        
        self._create_output_structure()
        
        try:
            self.load_all_data()
        except Exception as e:
            print(f"❌ Errore nel caricamento dati: {e}")
            return
        
        # Check if we have entity_id column for per-device analysis
        if 'entity_id' not in self.all_data.columns:
            print("⚠️  Colonna entity_id non trovata - creo report aggregato")
            self._create_general_report()
            return
        
        # Get unique devices
        unique_devices = self.all_data['entity_id'].unique()
        print(f"\n📱 Dispositivi trovati: {len(unique_devices)}")
        
        for device_id in unique_devices:
            device_data = self.all_data[self.all_data['entity_id'] == device_id].copy()
            friendly_name = device_data['friendly_name'].iloc[0] if 'friendly_name' in device_data.columns and len(device_data) > 0 else device_id
            
            print(f"\n📊 Analizzando dispositivo: {friendly_name}")
            print(f"   Entity ID: {device_id}")
            print(f"   Dati: {len(device_data)} righe")
            
            # Create device-specific report
            self._create_device_report(device_id, friendly_name, device_data)
        
        print(f"\n✅ Analisi completata per {len(unique_devices)} dispositivi")
        
        # Riepilogo finale
        print("\n" + "=" * 60)
        print("✅ ANALISI COMPLETATA CON SUCCESSO!")
        print("=" * 60)
        print(f"\n📋 RIEPILOGO OUTPUT GENERATI:")
        print(f"  • File CSV elaborati: {len(self.data_files)}")
        print(f"  • Report giornalieri PDF: {len(unique_dates)}")
        print(f"  • Report generale PDF: 1 (sempre aggiornato)")
        print(f"  • Dati totali analizzati: {len(self.all_data):,} righe")
        print(f"  • Grafici generati: {len(unique_dates) * 3 + 3} file PNG")
        print(f"\n📍 PERCORSI PRINCIPALI:")
        print(f"  • Report giornalieri: {self.daily_reports_dir}")
        print(f"  • Report generale: {self.general_report_dir}")
        print(f"  • File PDF principale: {self.general_report_dir / 'report_generale.pdf'}")
        print("\n🎯 CARATTERISTICHE REPORT PDF:")
        print("  ✓ Copertina professionale")
        print("  ✓ Indice automatico")
        print("  ✓ Tabelle dati formattate")
        print("  ✓ Grafici incorporati")
        print("  ✓ Raccomandazioni dettagliate")
        print("  ✓ Piano di azione")
        print("  ✓ Appendice tecnica")
        print("  ✓ SEMPRE AGGIORNATO (sovrascrive la versione precedente)")
        print("=" * 60)


def main():
    print("=" * 60)
    print("SHELLY ENERGY ANALYZER - REPORT PDF PROFESSIONALI")
    print("=" * 60)
    
    print("\n🎯 Questo programma genera report PDF professionali:")
    print("  1. Report giornalieri in reports/giornalieri/")
    print("  2. Report generale SEMPRE AGGIORNATO in reports/generale/")
    print("  3. Tutto in formato PDF con grafici incorporati")
    print("  4. Correzione automatica timestamp errati")
    print("  5. Report generale sovrascritto ad ogni esecuzione")
    print("=" * 60)
    
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"\n❌ Cartella 'data' non trovata.")
        create_folder = input("   Vuoi che crei la cartella 'data'? (s/n): ").lower()
        if create_folder == 's':
            data_dir.mkdir(exist_ok=True)
            print(f"   ✅ Cartella 'data' creata.")
            print(f"   📁 Inserisci i file CSV nella cartella 'data/' e riesegui il programma.")
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
        print(f"\n❌ Errore durante l'analisi: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Verifica dipendenze
    try:
        from reportlab.lib.pagesizes import A4
        print("✅ Tutte le dipendenze sono installate correttamente.")
    except ImportError:
        print("\n❌ REPORTLAB non installato!")
        print("   Installa con: pip install reportlab")
        exit(1)
    
    main()