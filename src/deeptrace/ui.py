import html
import json
import sqlite3
import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QIcon
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
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __version__
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
QTreeWidget::item:alternate { background: #192435; }
QHeaderView::section { background: #223249; padding: 8px; border: 0; }
QComboBox, QSpinBox, QLineEdit { padding: 7px; background: #1b293b; border: 1px solid #425a75;
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
    stage_started = Signal(int, int, str)
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
                self.level,
                self.symptom,
                self.timeout,
                self.cancel,
                self.progress.emit,
                started=self.stage_started.emit,
            )
            self.completed.emit(scan)
        except Exception:
            self.failed.emit("L'analyse a échoué ; aucun changement système effectué.")


class UpdateThread(QThread):
    checked = Signal(object)
    ready = Signal(object, object)
    download_progress = Signal(int, int)
    failed = Signal(str)

    def __init__(self, directory, download=False, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.download = download
        self.cancel = Event()

    def run(self):
        from .updates import UpdateError, check_latest, download_release

        try:
            release = check_latest()
            if self.cancel.is_set():
                return
            self.checked.emit(release)
            if release and self.download:
                staged = download_release(
                    release, self.directory, self.download_progress.emit, self.cancel
                )
                if not self.cancel.is_set():
                    self.ready.emit(staged, release)
        except UpdateError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("Vérification indisponible ; la version actuelle reste utilisable.")


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path, engine=None):
        super().__init__()
        self.setWindowTitle("DeepTrace — Diagnostic Windows local")
        icon = Path(__file__).parent / "assets" / "deeptrace.ico"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1320, 880)
        self.setMinimumSize(1000, 680)
        self.setStyleSheet(STYLE)
        self.engine = engine or ScanEngine()
        self.history = History(data_dir / "history.sqlite3")
        self.data_dir = data_dir
        self.preferences = self.history.get_settings()
        self.scan: Scan | None = None
        self.worker = None
        self.close_when_finished = False
        self.update_worker = None
        self.pending_update = None
        self.update_install_requested = False
        self.domain_views = {}
        self.domain_searches = {}
        self._render_scan_id = None
        self._domain_render_keys = {}
        self._detail_key = None
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
        left.addWidget(label(f"V{__version__} • local • lecture seule", "muted"))
        layout.addLayout(left)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.build_dashboard()
        for domain in dict.fromkeys(spec.domain for spec in CATALOG):
            page, box = self.page(domain)
            specs = [s for s in CATALOG if s.domain == domain]
            box.addWidget(label("\n".join(f"{s.title} : {s.purpose}" for s in specs), "muted"))
            view = browser()
            view.setPlainText(
                "Ouvrez cette rubrique après l'analyse pour consulter ses observations."
            )
            search = QLineEdit()
            search.setPlaceholderText("Rechercher dans les observations…")
            search.setAccessibleName(f"Rechercher dans {domain}")
            search.textChanged.connect(lambda text, target=view: self.find_in_view(target, text))
            self.domain_searches[domain] = search
            box.addWidget(search)
            self.domain_views[domain] = view
            box.addWidget(view, 1)
        self.build_repairs()
        self.build_protection()
        self.build_history()
        self.build_settings()
        self.navigation.currentRowChanged.connect(self.change_page)
        self.navigation.setCurrentRow(0)
        for signal in (
            self.expert.toggled,
            self.remember.toggled,
            self.timeout.valueChanged,
            self.level.currentTextChanged,
            self.symptom.currentTextChanged,
            self.check_updates.toggled,
            self.auto_updates.toggled,
        ):
            signal.connect(self.save_preferences)
        self.render()
        if getattr(sys, "frozen", False):
            QTimer.singleShot(0, self.startup_updates)

    def save_preferences(self, *_):
        settings = {
            "expert": self.expert.isChecked(),
            "remember": self.remember.isChecked(),
            "timeout": self.timeout.value(),
            "level": self.level.currentText(),
            "symptom": self.symptom.currentText(),
            "check_updates": self.check_updates.isChecked(),
            "auto_updates": self.auto_updates.isChecked(),
            "updates_consent": self.preferences.get("updates_consent", False),
            "export_directory": self.preferences.get("export_directory", ""),
        }
        try:
            self.history.save_settings(settings)
            self.preferences = settings
        except (OSError, ValueError, sqlite3.Error):
            self.state.setText("Les préférences s'appliquent, mais leur enregistrement a échoué.")

    @staticmethod
    def find_in_view(view, text):
        cursor = view.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        view.setTextCursor(cursor)
        if text:
            view.find(text)

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
        self.system_summary = label(
            "Pour commencer, lancez l'analyse rapide : inventaire matériel, Windows, stockage et "
            "protections. Les observations restent sur cet ordinateur.",
            "muted",
        )
        box.addWidget(self.system_summary)
        controls = QHBoxLayout()
        self.level = QComboBox()
        self.level.addItems(["rapide", "approfondie", "ciblée"])
        self.level.setCurrentText(self.preferences.get("level", "rapide"))
        self.level.setAccessibleName("Niveau d'analyse")
        self.symptom = QComboBox()
        self.symptom.addItems(list(SYMPTOMS))
        self.symptom.setCurrentText(self.preferences.get("symptom", next(iter(SYMPTOMS))))
        self.symptom.setAccessibleName("Symptôme à investiguer")
        self.symptom.setVisible(self.level.currentText() == "ciblée")
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
        self.analysis_description = label("", "muted")
        self.level.currentTextChanged.connect(self.update_analysis_description)
        self.symptom.currentTextChanged.connect(self.update_analysis_description)
        self.update_analysis_description()
        box.addWidget(self.analysis_description)
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
        self.results.setRootIsDecorated(False)
        self.results.setAlternatingRowColors(True)
        self.detail = browser()
        self.detail.setAccessibleName("Preuves et explications du contrôle sélectionné")
        self.result_filter = QComboBox()
        self.result_filter.addItems(
            ["Tous les contrôles", "Alertes uniquement", "Contrôles non aboutis"]
        )
        self.result_filter.setAccessibleName("Filtrer les résultats")
        self.result_filter.currentIndexChanged.connect(self.apply_result_filter)
        box.addWidget(self.result_filter)
        split.addWidget(self.results)
        split.addWidget(self.detail)
        split.setSizes([260, 280])
        box.addWidget(split, 1)

    def update_analysis_description(self, *_):
        level = self.level.currentText()
        count = len(select_collectors(level, self.symptom.currentText()))
        descriptions = {
            "rapide": "Inventaire et contrôles légers, sans test de charge.",
            "approfondie": "Ajoute événements, services, pilotes et logiciels ; "
            "plusieurs minutes possibles.",
            "ciblée": f"Dossier d'investigation : {self.symptom.currentText()}.",
        }
        self.analysis_description.setText(f"{count} contrôles • {descriptions[level]}")

    def apply_result_filter(self, *_):
        selected = self.result_filter.currentIndex()
        for index in range(self.results.topLevelItemCount()):
            item = self.results.topLevelItem(index)
            result = next(
                (
                    r
                    for r in self.scan.results
                    if r.collector_id == item.data(0, Qt.ItemDataRole.UserRole)
                ),
                None,
            )
            item.setHidden(
                bool(
                    result
                    and (
                        (selected == 1 and not result.findings)
                        or (selected == 2 and result.status == Status.OK)
                    )
                )
            )
        current = self.results.currentItem()
        if current is None or current.isHidden():
            visible = next(
                (
                    self.results.topLevelItem(i)
                    for i in range(self.results.topLevelItemCount())
                    if not self.results.topLevelItem(i).isHidden()
                ),
                None,
            )
            self.results.setCurrentItem(visible)
            if visible is None and self.scan:
                self.detail.setPlainText("Aucun contrôle ne correspond au filtre sélectionné.")

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
        self.history_list.itemDoubleClicked.connect(lambda _item: self.load_scan())
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        box.addWidget(scroll, 1)
        box = QVBoxLayout(content)
        self.expert = QCheckBox(
            "Mode expert : sources, commandes exactes et données brutes locales"
        )
        self.expert.setChecked(self.preferences.get("expert", False))
        self.expert.toggled.connect(self.render)
        box.addWidget(self.expert)
        box.addWidget(
            label("Délai maximal par collecteur (secondes, limité aussi par le catalogue)")
        )
        self.timeout = QSpinBox()
        self.timeout.setRange(1, 120)
        self.timeout.setValue(self.preferences.get("timeout", 25))
        box.addWidget(self.timeout)
        self.remember = QCheckBox("Conserver les prochaines analyses dans l'historique local")
        self.remember.setChecked(self.preferences.get("remember", True))
        box.addWidget(self.remember)
        self.check_updates = QCheckBox("Vérifier les mises à jour GitHub à chaque démarrage")
        self.check_updates.setChecked(self.preferences.get("check_updates", False))
        box.addWidget(self.check_updates)
        self.auto_updates = QCheckBox(
            "Installer puis redémarrer automatiquement après les analyses"
        )
        self.auto_updates.setChecked(self.preferences.get("auto_updates", False))
        self.auto_updates.setEnabled(self.check_updates.isChecked())
        self.auto_updates.toggled.connect(self.auto_update_option_changed)
        box.addWidget(self.auto_updates)
        self.check_updates.toggled.connect(self.update_options_changed)
        self.update_button = QPushButton("Vérifier les mises à jour maintenant")
        self.update_button.clicked.connect(lambda: self.start_update_check())
        box.addWidget(self.update_button)
        self.update_status = label(
            "Les diagnostics fonctionnent hors ligne. Les mises à jour utilisent uniquement "
            "les versions publiées dans Seiha1337/DeepTrace sur GitHub.",
            "muted",
        )
        box.addWidget(self.update_status)
        self.install_update_button = QPushButton("Installer la mise à jour et redémarrer")
        self.install_update_button.setVisible(False)
        self.install_update_button.clicked.connect(lambda: self.start_update_check(download=True))
        box.addWidget(self.install_update_button)
        notices = QPushButton("Composants embarqués et licences")
        notices.clicked.connect(self.show_licenses)
        box.addWidget(notices)
        box.addWidget(
            label(
                f"Historique : {self.history.path}\n"
                "Les noms de logiciels, composants et processus restent locaux. "
                "Les exports partagés "
                "contiennent uniquement une synthèse filtrée. Le stockage local "
                "n'est pas chiffré par "
                "DeepTrace ; il dépend des protections de votre compte Windows. "
                "Les préférences sont mémorisées localement. "
                "Aucun droit administrateur n'est demandé."
            )
        )
        box.addStretch()

    def show_licenses(self):
        root = Path(__file__).parent / "assets/licenses"
        if not root.exists():
            root = Path(__file__).resolve().parents[2] / "docs/licenses"
        view = QMessageBox(self)
        view.setWindowTitle("DeepTrace — composants embarqués")
        view.setText(
            "Python 3.13.17 (PSF), Qt / PySide6 Essentials 6.12.0 (LGPLv3), "
            "shiboken6 et PyInstaller 6.22.3 (GPL avec exception de bootloader). "
            "Sources et reconstruction : github.com/Seiha1337/DeepTrace, docs/THIRD_PARTY.md."
        )
        if root.exists():
            view.setDetailedText(
                "\n\n".join(
                    f"=== {path.name} ===\n{path.read_text('utf-8')}"
                    for path in sorted(root.glob("*.txt"))
                )
            )
        view.exec()

    def update_options_changed(self, enabled):
        if not enabled:
            self.auto_updates.setChecked(False)
            if self.update_worker:
                self.update_worker.cancel.set()
        self.auto_updates.setEnabled(enabled)
        self.preferences["updates_consent"] = True

    def auto_update_option_changed(self, enabled):
        if not enabled:
            self.update_install_requested = False
            self.pending_update = None
            if self.update_worker:
                self.update_worker.cancel.set()

    def startup_updates(self):
        if not self.preferences.get("updates_consent", False):
            answer = QMessageBox.question(
                self,
                "Mises à jour de DeepTrace",
                "Autoriser la vérification des versions sur GitHub à chaque démarrage, puis "
                "leur téléchargement et le redémarrage automatique quand aucune analyse "
                "n'est en cours ? Aucun diagnostic n'est envoyé. L'ancienne version est "
                "conservée avant remplacement. Vous pouvez désactiver cette option "
                "dans Paramètres.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            self.preferences["updates_consent"] = True
            enabled = answer == QMessageBox.StandardButton.Yes
            self.check_updates.setChecked(enabled)
            self.auto_updates.setChecked(enabled)
            self.save_preferences()
        if self.check_updates.isChecked():
            self.start_update_check()

    def start_update_check(self, download=False):
        if self.update_worker is not None:
            return
        self.update_install_requested = download or self.auto_updates.isChecked()
        self.update_status.setText("Vérification des versions publiées sur GitHub…")
        self.update_button.setEnabled(False)
        self.install_update_button.setVisible(False)
        self.update_worker = UpdateThread(
            self.data_dir / "updates",
            self.update_install_requested and getattr(sys, "frozen", False),
            self,
        )
        self.update_worker.checked.connect(self.on_update_checked)
        self.update_worker.ready.connect(self.on_update_ready)
        self.update_worker.failed.connect(self.update_status.setText)
        self.update_worker.download_progress.connect(self.on_update_download_progress)
        self.update_worker.finished.connect(self.on_update_finished)
        self.update_worker.start()

    def on_update_checked(self, release):
        if release is None:
            self.update_status.setText(
                f"Version {__version__} • aucune version plus récente publiée trouvée."
            )
            return
        if self.update_install_requested and getattr(sys, "frozen", False):
            self.update_status.setText(
                f"DeepTrace {release.version} • téléchargement et vérification…"
            )
        else:
            self.update_status.setText(f"DeepTrace {release.version} disponible sur GitHub.")
            self.install_update_button.setVisible(getattr(sys, "frozen", False))

    def on_update_download_progress(self, done, total):
        self.update_status.setText(f"Téléchargement de la mise à jour : {done / max(total, 1):.0%}")

    def on_update_ready(self, staged, release):
        self.pending_update = (staged, release)
        self.update_status.setText("Mise à jour vérifiée • redémarrage dès la fin des analyses.")

    def on_update_finished(self):
        self.update_worker.deleteLater()
        self.update_worker = None
        self.update_button.setEnabled(True)
        if self.close_when_finished and self.worker is None:
            self.close()
        elif self.worker is None:
            self.apply_pending_update()

    def apply_pending_update(self):
        if not self.pending_update or self.worker is not None or self.update_worker is not None:
            return
        from .updates import UpdateError, launch_installer

        staged, release = self.pending_update
        self.pending_update = None
        if not self.update_install_requested:
            return
        try:
            self.installer = launch_installer(staged, release, data_dir=self.data_dir)
        except (UpdateError, OSError):
            self.update_status.setText(
                "Installation impossible ; la version actuelle reste utilisable."
            )
            return
        self.close()

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
        self.symptom.setEnabled(False)
        self.remember_current_scan = self.remember.isChecked()
        self.cancel_button.setEnabled(True)
        self.state.setText("Analyse en cours • le premier contrôle démarre")
        self.worker = ScanThread(self.engine, level, self.scan.symptom, self.timeout.value(), self)
        self.worker.stage_started.connect(self.on_stage_started)
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_stage_started(self, current, total, collector_id):
        self.state.setText(
            f"Contrôle {current}/{total} en cours • {BY_ID[collector_id].title} • lecture seule"
        )

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
        if self.remember_current_scan:
            try:
                self.history.save(scan)
                self.refresh_history()
            except (OSError, ValueError, sqlite3.Error):
                self.state.setText("Analyse terminée ; enregistrement de l'historique impossible.")
        self.render()

    def on_failed(self, message):
        self.state.setText(message)

    def on_finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.start_button.setEnabled(True)
        self.level.setEnabled(True)
        self.symptom.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.export_button.setEnabled(bool(self.scan and self.scan.finished_at))
        if self.close_when_finished:
            self.close()
        else:
            self.apply_pending_update()

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
        scan_id = self.scan.id if self.scan else None
        if scan_id != self._render_scan_id:
            self._domain_render_keys.clear()
            self._detail_key = None
            self._render_scan_id = scan_id
            for view in self.domain_views.values():
                view.clear()
        selected = self.results.currentItem()
        selected_id = selected.data(0, Qt.ItemDataRole.UserRole) if selected else None
        self.results.blockSignals(True)
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
            if result.findings:
                item.setForeground(3, QColor("#ffd384"))
                item.setToolTip(3, "\n".join(f.title for f in result.findings))
            if result.status not in (Status.OK, Status.CANCELLED):
                item.setForeground(1, QColor("#ffd384"))
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
        self.apply_result_filter()
        self.results.blockSignals(False)
        self.show_selected(self.results.currentItem(), None)
        windows = next(
            (
                r.data[0]
                for r in results
                if r.collector_id == "windows" and r.status == Status.OK and r.data
            ),
            {},
        )
        hardware = next(
            (r.data for r in results if r.collector_id == "hardware" and r.status == Status.OK), []
        )
        cpu = next((r.get("Name") for r in hardware if r.get("Kind") == "CPU"), None)
        gpu = next((r.get("Name") for r in hardware if r.get("Kind") == "GPU"), None)
        summary = [str(value) for value in (windows.get("Caption"), cpu, gpu) if value]
        memory = windows.get("TotalVisibleMemorySize")
        if isinstance(memory, (int, float)) and not isinstance(memory, bool):
            summary.append(f"{memory / 1024**2:.1f} Gio de RAM")
        if summary:
            self.system_summary.setText(" • ".join(summary))
        elif self.scan:
            self.system_summary.setText("Résumé système indisponible dans les contrôles exécutés.")
        self.render_visible_domain()
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
            signature = (self.scan.id, key, id(result), self.expert.isChecked())
            if result and signature != self._detail_key:
                self.detail.setHtml(self.result_html(result))
                self._detail_key = signature

    def change_page(self, index):
        self.pages.setCurrentIndex(index)
        self.render_visible_domain()

    def render_visible_domain(self):
        item = self.navigation.currentItem()
        domain = item.text() if item else None
        if domain not in self.domain_views:
            return
        results = self.scan.results if self.scan else []
        relevant = [r for r in results if BY_ID[r.collector_id].domain == domain]
        signature = (
            self.scan.id if self.scan else None,
            self.expert.isChecked(),
            tuple(id(r) for r in relevant),
        )
        if self._domain_render_keys.get(domain) == signature:
            return
        view = self.domain_views[domain]
        view.setHtml(
            "".join(self.result_html(r) for r in relevant)
            or "<p>Aucun contrôle de ce domaine exécuté dans l'analyse sélectionnée.</p>"
        )
        self._domain_render_keys[domain] = signature
        self.find_in_view(view, self.domain_searches[domain].text())

    def export(self):
        if not self.scan or not self.scan.finished_at:
            return
        filename, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter la synthèse filtrée",
            str(
                Path(self.preferences.get("export_directory") or Path.home())
                / "deeptrace-rapport.html"
            ),
            "Rapport HTML (*.html);;Données JSON (*.json)",
        )
        if filename:
            try:
                target = Path(filename)
                if not target.suffix:
                    target = target.with_suffix(".json" if "JSON" in selected_filter else ".html")
                    if (
                        target.exists()
                        and QMessageBox.question(
                            self,
                            "Remplacer le rapport",
                            f"Le fichier {target.name} existe. Le remplacer ?",
                        )
                        != QMessageBox.StandardButton.Yes
                    ):
                        return
                export_report(self.scan, target)
                self.preferences["export_directory"] = str(target.parent)
                self.save_preferences()
                self.state.setText("Synthèse filtrée exportée • aucune donnée brute incluse")
            except (OSError, ValueError):
                QMessageBox.warning(
                    self, "Export impossible", "Vérifiez l'extension et l'accès au fichier."
                )

    def refresh_history(self):
        try:
            scans = self.history.list_scans()
            simulations = self.history.simulations()
        except (OSError, ValueError, sqlite3.Error):
            self.history_detail.setPlainText(
                "L'historique ne peut pas être lu. Les analyses en cours restent disponibles "
                "dans cette fenêtre ; aucune donnée existante n'a été effacée."
            )
            return
        self.history_list.clear()
        for scan_id, started, level in scans:
            item = QListWidgetItem(
                f"{started[:19].replace('T', ' ')} UTC • {level} • {scan_id[:8]}"
            )
            item.setData(Qt.ItemDataRole.UserRole, scan_id)
            self.history_list.addItem(item)
        self.history_detail.setPlainText(
            "\n\n".join(
                f"{r['created_at']} • {r['operation']} • {r['state']}\n{r['state_after']}"
                for r in simulations
            )
            or "Aucune simulation journalisée."
        )

    def load_scan(self):
        items = self.history_list.selectedItems()
        if self.worker:
            self.history_detail.setPlainText(
                "Attendez la fin de l'analyse en cours avant de charger l'historique."
            )
            return
        if len(items) != 1:
            self.history_detail.setPlainText(
                "Sélectionnez une analyse à charger, ou double-cliquez dessus."
            )
            return
        try:
            self.scan = self.history.load(items[0].data(Qt.ItemDataRole.UserRole))
            self.render()
            self.export_button.setEnabled(bool(self.scan.finished_at))
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
        try:
            scans = sorted(
                (self.history.load(i.data(Qt.ItemDataRole.UserRole)) for i in items),
                key=lambda s: s.started_at,
            )
            changes = compare(*scans)
        except (KeyError, ValueError, OSError, sqlite3.Error):
            self.history_detail.setPlainText(
                "Comparaison impossible : l'une des analyses n'est plus disponible "
                "ou est endommagée."
            )
            return
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
            try:
                for item in items:
                    self.history.delete(item.data(Qt.ItemDataRole.UserRole))
            except (OSError, sqlite3.Error):
                QMessageBox.warning(
                    self, "Historique", "Certaines analyses n'ont pas pu être supprimées."
                )
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
        if self.worker is not None or self.update_worker is not None:
            self.close_when_finished = True
            self.cancel_scan()
            if self.update_worker:
                self.update_worker.cancel.set()
            self.state.setText(
                "Fermeture demandée • attente de la fin ou du délai du contrôle courant"
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
