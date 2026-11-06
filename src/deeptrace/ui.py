import html
import json
import sqlite3
from pathlib import Path
from threading import Event

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .catalog import BY_ID, CATALOG, SYMPTOMS, select_collectors
from .engine import ScanEngine
from .interventions import OPERATIONS, PROTECTIONS, simulate
from .models import Scan, Status
from .report import export_report
from .runner import script_for
from .storage import History, compare

STYLE = """
QWidget { background: #101722; color: #e7edf5; font-family: 'Segoe UI'; font-size: 14px; }
QMainWindow { background: #101722; }
QLabel#brand { font-size: 27px; font-weight: 700; color: #69e4ce; }
QLabel#title { font-size: 28px; font-weight: 650; }
QLabel#muted { color: #a9b9cb; }
QFrame#card { background: #192435; border: 1px solid #304158; border-radius: 12px; }
QFrame#card QLabel { background: transparent; }
QLabel#metric { font-size: 30px; color: #69e4ce; font-weight: 700; }
QPushButton { padding: 10px 16px; background: #25364c; border: 1px solid #425a75;
 border-radius: 7px; }
QPushButton:hover { background: #344b66; }
QPushButton#primary { background: #60dbc3; color: #0a2027; font-weight: 700; }
QPushButton:disabled { color: #8293a5; background: #1b2838; }
QPushButton:focus, QComboBox:focus, QSpinBox:focus { border: 2px solid #69e4ce; }
QListWidget { background: #141e2c; border: 0; border-radius: 8px; padding: 6px; }
QListWidget::item { padding: 10px 12px; border-radius: 6px; }
QListWidget::item:selected { background: #25454f; color: #82f2dc; }
QTreeWidget, QTextBrowser { background: #141e2c; border: 1px solid #304158;
 border-radius: 8px; padding: 8px; selection-background-color: #25454f; }
QHeaderView::section { background: #223249; padding: 8px; border: 0; }
QComboBox, QSpinBox { padding: 7px; background: #1b293b; border: 1px solid #425a75;
 border-radius: 5px; }
QProgressBar { background: #1b293b; border: 0; border-radius: 5px; text-align: center; }
QProgressBar::chunk { background: #319d8a; border-radius: 5px; }
QCheckBox { spacing: 8px; }
"""

FIELD_LABELS = {
    "Caption": "Système",
    "Version": "Version",
    "BuildNumber": "Build",
    "OSArchitecture": "Architecture",
    "TotalVisibleMemorySize": "Mémoire physique totale",
    "FreePhysicalMemory": "Mémoire physique disponible",
    "LastBootUpTime": "Dernier démarrage UTC",
    "Kind": "Type",
    "Name": "Nom",
    "Manufacturer": "Fabricant",
    "Capacity": "Capacité",
    "Speed": "Vitesse déclarée (MHz)",
    "Cores": "Cœurs",
    "Threads": "Processeurs logiques",
    "DriverVersion": "Version du pilote",
    "DeviceID": "Volume",
    "Size": "Capacité",
    "FreeSpace": "Espace libre",
    "FileSystem": "Système de fichiers",
    "MediaType": "Support",
    "BusType": "Bus",
    "HealthStatus": "État de santé déclaré",
    "OperationalStatus": "État opérationnel déclaré",
    "LoadPercentage": "Charge CPU (%)",
    "WorkingSetBytes": "Mémoire résidente",
    "InterfaceDescription": "Interface",
    "Status": "État",
    "LinkSpeed": "Vitesse de liaison déclarée",
    "AMServiceEnabled": "Service antimalware actif",
    "AntivirusEnabled": "Antivirus Defender actif",
    "RealTimeProtectionEnabled": "Protection temps réel Defender active",
    "AntivirusSignatureLastUpdated": "Dernière mise à jour des signatures UTC",
    "Enabled": "Activé",
    "Id": "Identifiant événement",
    "ProviderName": "Fournisseur",
    "Level": "Niveau Windows",
    "TimeCreated": "Date UTC",
    "DeviceName": "Périphérique",
    "IsSigned": "Signature déclarée",
    "DisplayName": "Logiciel",
    "DisplayVersion": "Version",
    "Publisher": "Éditeur",
    "State": "État",
    "StartMode": "Mode de démarrage",
}


def display_value(key, value):
    if value is None:
        return "Indisponible"
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, (int, float)):
        if key in ("Size", "FreeSpace", "Capacity", "WorkingSetBytes"):
            return f"{value / 1024**3:.2f} Gio ({value} octets)"
        if key in ("TotalVisibleMemorySize", "FreePhysicalMemory"):
            return f"{value / 1024**2:.2f} Gio ({value} Kio)"
    return str(value)


def label(text: str, name="", wrap=True) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    if name:
        widget.setObjectName(name)
    return widget


def browser() -> QTextBrowser:
    view = QTextBrowser()
    view.setOpenExternalLinks(False)
    view.setOpenLinks(False)
    return view


class ScanThread(QThread):
    progress = Signal(int, int, object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, engine, level, symptom, timeout, parent=None):
        super().__init__(parent)
        self.engine, self.level, self.symptom, self.timeout = engine, level, symptom, timeout
        self.cancel = Event()

    def run(self):
        try:
            scan = self.engine.scan(
                self.level, self.symptom, self.timeout, self.cancel, self.progress.emit
            )
            self.completed.emit(scan)
        except Exception:
            self.failed.emit("L'analyse a échoué ; aucun changement système effectué.")


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path, engine=None):
        super().__init__()
        self.setWindowTitle("DeepTrace — Diagnostic Windows local")
        self.resize(1320, 880)
        self.setMinimumSize(1000, 680)
        self.setStyleSheet(STYLE)
        self.engine = engine or ScanEngine()
        self.history = History(data_dir / "history.sqlite3")
        self.scan: Scan | None = None
        self.worker = None
        self.domain_views = {}
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(16, 16, 20, 16)
        self.navigation = QListWidget()
        self.navigation.setAccessibleName("Navigation principale")
        self.navigation.setFixedWidth(245)
        self.navigation.setWordWrap(True)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left = QVBoxLayout()
        left.addWidget(label("◈ DeepTrace", "brand"))
        left.addWidget(label("Comprendre. Expliquer. Vérifier.", "muted"))
        left.addSpacing(14)
        left.addWidget(self.navigation, 1)
        left.addWidget(label("V0.1 • local • lecture seule", "muted"))
        layout.addLayout(left)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.build_dashboard()
        for domain in dict.fromkeys(spec.domain for spec in CATALOG):
            page, box = self.page(domain)
            specs = [s for s in CATALOG if s.domain == domain]
            box.addWidget(label("\n".join(f"{s.title} : {s.purpose}" for s in specs), "muted"))
            view = browser()
            self.domain_views[domain] = view
            box.addWidget(view, 1)
        self.build_repairs()
        self.build_protection()
        self.build_history()
        self.build_settings()
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.render()

    def page(self, title):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 8, 0, 0)
        box.setSpacing(14)
        box.addWidget(label(title, "title"))
        self.navigation.addItem(title)
        self.pages.addWidget(page)
        return page, box

    def build_dashboard(self):
        _, box = self.page("Tableau de bord")
        box.addWidget(label("Des observations vérifiables, avant toute décision.", "muted"))
        cards = QHBoxLayout()
        self.metrics = []
        for title in ("Contrôles terminés", "Alertes à examiner", "Contrôles non aboutis"):
            card = QFrame()
            card.setObjectName("card")
            inner = QVBoxLayout(card)
            metric = label("—", "metric")
            self.metrics.append(metric)
            inner.addWidget(metric)
            inner.addWidget(label(title, "muted"))
            cards.addWidget(card)
        box.addLayout(cards)
        box.addWidget(
            label(
                "Aucun score de santé : les compteurs décrivent uniquement la "
                "couverture de l'analyse. "
                "Aucun diagnostic ne démarre à l'ouverture."
            )
        )
        controls = QHBoxLayout()
        self.level = QComboBox()
        self.level.addItems(["rapide", "approfondie", "ciblée"])
        self.level.setAccessibleName("Niveau d'analyse")
        self.symptom = QComboBox()
        self.symptom.addItems(list(SYMPTOMS))
        self.symptom.setAccessibleName("Symptôme à investiguer")
        self.symptom.setVisible(False)
        self.level.currentTextChanged.connect(
            lambda text: self.symptom.setVisible(text == "ciblée")
        )
        controls.addWidget(self.level)
        controls.addWidget(self.symptom)
        box.addLayout(controls)
        actions = QHBoxLayout()
        self.start_button = QPushButton("Lancer l'analyse")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start_scan)
        actions.addWidget(self.start_button)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_scan)
        actions.addWidget(self.cancel_button)
        self.export_button = QPushButton("Exporter une synthèse…")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export)
        actions.addWidget(self.export_button)
        box.addLayout(actions)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        box.addWidget(self.progress_bar)
        self.state = label("Prêt • aucune modification du système", "muted")
        box.addWidget(self.state)
        split = QSplitter(Qt.Orientation.Vertical)
        self.results = QTreeWidget()
        self.results.setHeaderLabels(["Contrôle", "État", "Durée", "Alertes"])
        self.results.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.setAccessibleName("Résultats des contrôles")
        self.results.currentItemChanged.connect(self.show_selected)
        self.detail = browser()
        self.detail.setAccessibleName("Preuves et explications du contrôle sélectionné")
        split.addWidget(self.results)
        split.addWidget(self.detail)
        split.setSizes([260, 280])
        box.addWidget(split, 1)

    def build_repairs(self):
        _, box = self.page("Centre de réparation")
        box.addWidget(
            label("Prévisualisation uniquement • aucune réparation réelle disponible.", "muted")
        )
        self.operation = QComboBox()
        for op in OPERATIONS.values():
            self.operation.addItem(op.title, op.id)
        box.addWidget(self.operation)
        view = browser()
        op = next(iter(OPERATIONS.values()))
        titles = (
            "Identifiant",
            "Opération",
            "Justification",
            "Conditions",
            "Privilèges",
            "Ressources concernées",
            "Modifications",
            "Risques",
            "Effets secondaires",
            "Redémarrage",
            "Vérifications préalables",
            "Protection",
            "Vérification après",
            "Retour arrière",
            "Limites",
        )
        view.setPlainText(
            "\n\n".join(
                f"{title} : {value}" for title, value in zip(titles, vars(op).values(), strict=True)
            )
        )
        box.addWidget(view, 1)
        button = QPushButton("Simuler et journaliser le plan")
        button.clicked.connect(self.simulate)
        box.addWidget(button)

    def build_protection(self):
        _, box = self.page("Sauvegardes et restauration")
        box.addWidget(
            label(
                "Centre d'information V0.1. Aucun outil de sauvegarde ni de "
                "restauration n'est exécuté.",
                "muted",
            )
        )
        view = browser()
        view.setHtml(
            "".join(
                f"<h2>{html.escape(title)}</h2><p>{html.escape(text)}</p>"
                for title, text in PROTECTIONS.items()
            )
        )
        box.addWidget(view, 1)

    def build_history(self):
        _, box = self.page("Historique")
        box.addWidget(
            label(
                "Données techniques conservées localement. Sélectionnez deux "
                "analyses pour les comparer. "
                "Aucune différence n'établit à elle seule un lien de cause à effet.",
                "muted",
            )
        )
        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        box.addWidget(self.history_list, 1)
        row = QHBoxLayout()
        for text, callback in (
            ("Charger", self.load_scan),
            ("Comparer deux analyses", self.compare),
            ("Supprimer la sélection…", self.delete_selected),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
        box.addLayout(row)
        self.history_detail = browser()
        box.addWidget(self.history_detail, 1)
        self.refresh_history()

    def build_settings(self):
        _, box = self.page("Paramètres et mode expert")
        self.expert = QCheckBox(
            "Mode expert : sources, commandes exactes et données brutes locales"
        )
        self.expert.toggled.connect(self.render)
        box.addWidget(self.expert)
        box.addWidget(
            label("Délai maximal par collecteur (secondes, limité aussi par le catalogue)")
        )
        self.timeout = QSpinBox()
        self.timeout.setRange(1, 120)
        self.timeout.setValue(25)
        box.addWidget(self.timeout)
        self.remember = QCheckBox("Conserver les prochaines analyses dans l'historique local")
        self.remember.setChecked(True)
        box.addWidget(self.remember)
        box.addWidget(
            label(
                f"Historique : {self.history.path}\n"
                "Les noms de logiciels, composants et processus restent locaux. "
                "Les exports partagés "
                "contiennent uniquement une synthèse filtrée. Le stockage local "
                "n'est pas chiffré par "
                "DeepTrace ; il dépend des protections de votre compte Windows. "
                "Les réglages de cette "
                "version s'appliquent à la session. Aucun droit administrateur n'est demandé."
            )
        )
        box.addStretch()

    def start_scan(self):
        if self.worker is not None:
            return
        level, symptom = self.level.currentText(), self.symptom.currentText()
        if (
            level != "rapide"
            and QMessageBox.question(
                self,
                "Analyse étendue en lecture seule",
                "Les requêtes étendues peuvent durer plusieurs minutes et solliciter WMI et les "
                "journaux. Aucun test de charge ni changement système. Continuer ?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.scan = Scan(level, symptom if level == "ciblée" else "")
        self.results.clear()
        self.progress_bar.setRange(0, len(select_collectors(level, symptom)))
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.level.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.state.setText("Analyse en cours • le premier contrôle démarre")
        self.worker = ScanThread(self.engine, level, self.scan.symptom, self.timeout.value(), self)
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def cancel_scan(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self.state.setText(
                "Annulation demandée • attente du contrôle courant ou de son délai maximal"
            )

    def on_progress(self, done, total, result):
        self.scan.results.append(result)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.state.setText(f"{done}/{total} étapes traitées • {BY_ID[result.collector_id].title}")
        self.render()

    def on_completed(self, scan):
        self.scan = scan
        self.state.setText(
            "Analyse interrompue • résultats partiels"
            if any(r.status == Status.CANCELLED for r in scan.results)
            else "Analyse terminée • consulter les alertes et les limites de couverture"
        )
        if self.remember.isChecked():
            try:
                self.history.save(scan)
                self.refresh_history()
            except (OSError, sqlite3.Error):
                self.state.setText("Analyse terminée ; enregistrement de l'historique impossible.")
        self.render()

    def on_failed(self, message):
        self.state.setText(message)

    def on_finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.start_button.setEnabled(True)
        self.level.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.export_button.setEnabled(bool(self.scan and self.scan.finished_at))

    def result_html(self, result):
        spec = BY_ID[result.collector_id]
        esc = html.escape
        parts = [
            f"<h2>{esc(spec.title)}</h2><p>{esc(spec.purpose)}</p>",
            f"<p><b>État :</b> {esc(result.status.value)}</p>",
        ]
        if result.error:
            parts.append(f"<p>{esc(result.error)}</p>")
        elif not result.findings:
            parts.append(
                "<p>Aucune alerte de règle. Aucune action nécessaire selon ces seules règles ; "
                "cela ne garantit pas l'absence de problème.</p>"
            )
        for finding in result.findings:
            parts.append(f"<h3>{esc(finding.title)}</h3>")
            labels = {
                "observed": "Fait observé",
                "interpretation": "Interprétation",
                "hypothesis": "Hypothèse",
                "severity": "Gravité",
                "confidence": "Confiance",
                "confirmation": "Vérification complémentaire",
                "recommendation": "Action recommandée",
                "optional_action": "Action facultative",
                "changes": "Modifications",
                "risks": "Risques",
                "protection": "Protection",
                "rollback": "Retour arrière",
                "verification": "Vérification après intervention",
            }
            for key, title in labels.items():
                parts.append(f"<p><b>{title} :</b> {esc(getattr(finding, key))}</p>")
            parts.append(
                f"<p><b>Preuves :</b> {esc(json.dumps(finding.evidence, ensure_ascii=False))}</p>"
            )
        parts.append(f"<p><b>Limites :</b> {esc(spec.limitations)}</p>")
        if self.expert.isChecked():
            parts.append(
                f"<p><b>Source :</b> {esc(spec.source)}<br>"
                f"<b>Prérequis :</b> {esc(spec.prerequisites)}<br>"
                f"<b>Privilèges :</b> {esc(spec.privileges)}<br>"
                f"<b>Impact :</b> {esc(spec.impact)}<br>"
                f"<b>Code de retour :</b> {result.return_code}</p>"
            )
            parts.append(f"<pre>{esc(script_for(spec.id))}</pre>")
        parts.append("<h3>Observations locales</h3>")
        if self.expert.isChecked():
            parts.append(
                "<pre>" + esc(json.dumps(result.data, indent=2, ensure_ascii=False)) + "</pre>"
            )
        else:
            for index, row in enumerate(result.data, 1):
                parts.append(f"<p><b>Observation {index}</b></p><table cellpadding='4'>")
                for key, value in row.items():
                    parts.append(
                        f"<tr><td>{esc(FIELD_LABELS.get(key, key))}</td>"
                        f"<td>{esc(display_value(key, value))}</td></tr>"
                    )
                parts.append("</table>")
        return "".join(parts)

    def render(self, *_):
        results = self.scan.results if self.scan else []
        selected = self.results.currentItem()
        selected_id = selected.data(0, Qt.ItemDataRole.UserRole) if selected else None
        self.results.clear()
        for result in results:
            spec = BY_ID[result.collector_id]
            item = QTreeWidgetItem(
                [
                    spec.title,
                    result.status.value,
                    f"{result.duration_ms / 1000:.2f} s",
                    str(len(result.findings)),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, spec.id)
            self.results.addTopLevelItem(item)
            if spec.id == selected_id:
                self.results.setCurrentItem(item)
        if self.results.currentItem() is None and results:
            self.results.setCurrentItem(self.results.topLevelItem(0))
        counts = (
            sum(r.status == Status.OK for r in results),
            sum(len(r.findings) for r in results),
            sum(r.status != Status.OK for r in results),
        )
        for metric, value in zip(self.metrics, counts, strict=True):
            metric.setText(str(value) if self.scan else "—")
        for domain, view in self.domain_views.items():
            relevant = [r for r in results if BY_ID[r.collector_id].domain == domain]
            view.setHtml(
                "".join(self.result_html(r) for r in relevant)
                or "<p>Aucun contrôle de ce domaine exécuté dans l'analyse sélectionnée.</p>"
            )
        if not results:
            self.detail.setPlainText(
                "Lancez une analyse, puis sélectionnez un contrôle pour lire ses "
                "preuves et ses limites. "
                "La collecte reste locale ; aucun score artificiel ni correction automatique."
            )

    def show_selected(self, current, _previous):
        if current and self.scan:
            key = current.data(0, Qt.ItemDataRole.UserRole)
            result = next((r for r in self.scan.results if r.collector_id == key), None)
            if result:
                self.detail.setHtml(self.result_html(result))

    def export(self):
        if not self.scan or not self.scan.finished_at:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter la synthèse filtrée",
            "deeptrace-rapport.html",
            "Rapport HTML (*.html);;Données JSON (*.json)",
        )
        if filename:
            try:
                export_report(self.scan, Path(filename))
                self.state.setText("Synthèse filtrée exportée • aucune donnée brute incluse")
            except (OSError, ValueError):
                QMessageBox.warning(
                    self, "Export impossible", "Vérifiez l'extension et l'accès au fichier."
                )

    def refresh_history(self):
        self.history_list.clear()
        for scan_id, started, level in self.history.list_scans():
            item = QListWidgetItem(
                f"{started[:19].replace('T', ' ')} UTC • {level} • {scan_id[:8]}"
            )
            item.setData(Qt.ItemDataRole.UserRole, scan_id)
            self.history_list.addItem(item)
        self.history_detail.setPlainText(
            "\n\n".join(
                f"{r['created_at']} • {r['operation']} • {r['state']}\n{r['state_after']}"
                for r in self.history.simulations()
            )
            or "Aucune simulation journalisée."
        )

    def load_scan(self):
        items = self.history_list.selectedItems()
        if len(items) != 1 or self.worker:
            return
        try:
            self.scan = self.history.load(items[0].data(Qt.ItemDataRole.UserRole))
            self.render()
            self.export_button.setEnabled(True)
            self.navigation.setCurrentRow(0)
            self.state.setText(
                f"Analyse historique chargée • {self.scan.started_at} • mesures non actuelles"
            )
        except (KeyError, ValueError, OSError, sqlite3.Error):
            QMessageBox.warning(self, "Historique", "Lecture de l'analyse impossible.")

    def compare(self):
        items = self.history_list.selectedItems()
        if len(items) != 2:
            self.history_detail.setPlainText("Sélectionnez exactement deux analyses (Ctrl + clic).")
            return
        scans = sorted(
            (self.history.load(i.data(Qt.ItemDataRole.UserRole)) for i in items),
            key=lambda s: s.started_at,
        )
        changes = compare(*scans)
        self.history_detail.setPlainText(
            "\n".join(f"{BY_ID[c['collector']].title} : {c['change']}" for c in changes)
            or "Aucun changement dans les données collectées ; aucune garantie de santé globale."
        )

    def delete_selected(self):
        items = self.history_list.selectedItems()
        if (
            items
            and QMessageBox.question(
                self,
                "Supprimer de l'historique",
                f"Supprimer les {len(items)} analyses sélectionnées ? "
                "Cette suppression ne touche aucun fichier système et ne peut pas être annulée.",
            )
            == QMessageBox.StandardButton.Yes
        ):
            for item in items:
                self.history.delete(item.data(Qt.ItemDataRole.UserRole))
            self.refresh_history()

    def simulate(self):
        try:
            if self.worker:
                raise ValueError("Attendre la fin de l'analyse.")
            record = simulate(self.operation.currentData(), self.scan.id if self.scan else None)
            self.history.record_simulation(record)
            self.refresh_history()
            QMessageBox.information(
                self,
                "Simulation terminée",
                "Plan journalisé. Aucun fichier supprimé, "
                "aucune sauvegarde créée, aucun problème déclaré corrigé.",
            )
        except (ValueError, sqlite3.Error) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Journalisation impossible."
            QMessageBox.warning(self, "Simulation indisponible", message)

    def closeEvent(self, event):
        if self.worker is not None:
            self.cancel_scan()
            QMessageBox.information(
                self,
                "Analyse en cours",
                "Annulation demandée. Attendez la fin du "
                "contrôle courant avant de fermer l'application.",
            )
            event.ignore()
        else:
            event.accept()


def launch(data_dir: Path):
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("DeepTrace")
    window = MainWindow(data_dir)
    window.show()
    code = app.exec()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return code
