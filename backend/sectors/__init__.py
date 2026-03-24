"""
sectors/__init__.py
All 6 sector configurations.
To add a new sector: add one SectorConfig entry to ALL_SECTORS. Nothing else changes.
"""
from dataclasses import dataclass
from typing import List, Tuple, Dict


@dataclass
class SectorConfig:
    id:          str
    label:       str
    accent:      str
    persona:     str
    terminology: Dict[str, str]
    patterns:    List[Tuple[str, str]]
    suggestions: List[str]


AGRICULTURE = SectorConfig(
    id="agriculture", label="Agriculture", accent="green",
    persona=(
        "You are an expert agricultural analyst and farm advisor. "
        "Help farmers, agronomists, and policymakers extract insights from crop reports, "
        "MSP documents, soil studies, and government schemes. "
        "Ground answers strictly in the provided document context. "
        "Mention relevant schemes (PM-KISAN, PMFBY) where appropriate. "
        "Never invent data — if not in the document, say so clearly."
    ),
    terminology={"workspace": "Farm workspace", "document": "Report",
                 "query": "Ask about your crops", "user_label": "Farmer / Analyst"},
    patterns=[
        (r'MSP[\s:]+(?:Rs\.?|₹)\s*[\d,]+',        "MSP value"),
        (r'(?:Rs\.?|₹)\s*[\d,]+\s*per\s*quintal',  "price per quintal"),
        (r'(?:Rs\.?|₹)\s*[\d,]+\s*per\s*hectare',  "price per hectare"),
        (r'\d+(?:\.\d+)?\s*(?:MT|quintal|tonne)',   "quantity"),
        (r'\d{4}-\d{2,4}\s*(?:kharif|rabi)',        "crop season"),
        (r'NDVI\s*[:=]\s*[\d.]+',                   "NDVI value"),
        (r'\d+(?:\.\d+)?\s*mm\s*rainfall',          "rainfall"),
        (r'(?:yield|production)[\s:]+[\d,]+',       "yield figure"),
    ],
    suggestions=[
        "What is the MSP for wheat this season?",
        "Summarise the crop yield report",
        "What government schemes are available?",
        "Compare production figures across documents",
        "What is the projected market price?",
        "What pesticide quantities are recommended?",
    ],
)

HEALTHCARE = SectorConfig(
    id="healthcare", label="Healthcare", accent="teal",
    persona=(
        "You are a clinical document analyst assisting healthcare professionals. "
        "Extract accurate information from medical records, clinical trial reports, "
        "drug information sheets, and hospital policy documents. "
        "Ground all answers strictly in the provided documents. "
        "Never provide medical advice — only summarise what the documents state. "
        "Flag any critical safety information clearly."
    ),
    terminology={"workspace": "Patient workspace", "document": "Medical record",
                 "query": "Ask about this record", "user_label": "Clinician"},
    patterns=[
        (r'\d+(?:\.\d+)?\s*mg(?:/\w+)?',               "dosage"),
        (r'\d+(?:\.\d+)?\s*ml(?:/\w+)?',               "volume"),
        (r'(?:BP|blood pressure)[\s:]+\d+/\d+',        "blood pressure"),
        (r'(?:HR|heart rate)[\s:]+\d+\s*bpm',          "heart rate"),
        (r'(?:temperature|temp)[\s:]+\d+(?:\.\d+)?',   "temperature"),
        (r'ICD-\d+(?:\.\w+)?',                          "ICD code"),
        (r'(?:diagnosis|dx)[\s:]+[A-Za-z\s]+',         "diagnosis"),
        (r'\d+(?:\.\d+)?\s*(?:years? old|y/?o)',       "patient age"),
    ],
    suggestions=[
        "What medications are prescribed?",
        "What is the patient diagnosis?",
        "Summarise the treatment plan",
        "What dosage is recommended?",
        "Are there drug interaction warnings?",
        "What are the follow-up instructions?",
    ],
)

EDUCATION = SectorConfig(
    id="education", label="Education", accent="purple",
    persona=(
        "You are an expert education analyst and academic advisor. "
        "Help students, teachers, and administrators extract information from "
        "syllabi, examination papers, research papers, and academic policies. "
        "Ground all answers in the provided documents only."
    ),
    terminology={"workspace": "Course workspace", "document": "Academic document",
                 "query": "Ask about your materials", "user_label": "Student / Educator"},
    patterns=[
        (r'\d+(?:\.\d+)?\s*(?:marks?|points?|credits?)', "marks/credits"),
        (r'(?:grade|GPA|CGPA)[\s:]+[A-F\d.]+',          "grade"),
        (r'(?:pass(?:ing)?)[\s]+marks?[\s:]+\d+',        "pass marks"),
        (r'(?:unit|chapter|module)\s+\d+',               "unit reference"),
        (r'(?:deadline|due date)[\s:]+\S+',              "deadline"),
        (r'(?:total\s+)?marks?[\s:]+\d+',                "total marks"),
        (r'(?:attendance)[\s:]+\d+(?:\.\d+)?\s*%',      "attendance"),
        (r'(?:semester|sem)\s+\d+',                      "semester"),
    ],
    suggestions=[
        "What topics are covered in this syllabus?",
        "What is the passing marks requirement?",
        "Summarise the exam pattern",
        "What are the assignment deadlines?",
        "Compare marking schemes across papers",
        "What are the learning outcomes?",
    ],
)

MILITARY = SectorConfig(
    id="military", label="Military", accent="red",
    persona=(
        "You are a military intelligence and documentation analyst. "
        "Help defence personnel extract precise information from operational orders, "
        "equipment manuals, procurement documents, and strategic reports. "
        "Be factual, concise, and structured. "
        "Ground all answers strictly in the provided documents."
    ),
    terminology={"workspace": "Operation workspace", "document": "Field document",
                 "query": "Query operational documents", "user_label": "Officer / Analyst"},
    patterns=[
        (r'(?:grid|coord(?:inate)?)[\s:]+\d{4,6}[A-Z]?', "grid reference"),
        (r'(?:ETA|ETD|ETE)[\s:]+\d{4}[LZ]?',             "time reference"),
        (r'(?:callsign|unit)[\s:]+[A-Z0-9\-]+',           "callsign/unit"),
        (r'(?:frequency|freq)[\s:]+[\d.]+\s*MHz',         "frequency"),
        (r'(?:serial|NSN)[\s:]+[\d\-]+',                  "serial/NSN"),
        (r'\d+(?:\.\d+)?\s*(?:km|nm|mi)\s*(?:range)?',   "distance"),
        (r'(?:authorised|classified)[\s:]+\w+',           "classification"),
        (r'SITREP[\s:]+\w+',                              "SITREP"),
    ],
    suggestions=[
        "What is the mission objective?",
        "What equipment is listed?",
        "Summarise the rules of engagement",
        "What are the logistical requirements?",
        "Compare specifications across documents",
        "What are the command structure details?",
    ],
)

HOUSEHOLD = SectorConfig(
    id="household", label="Household", accent="amber",
    persona=(
        "You are a helpful home management assistant. "
        "Help homeowners extract information from property documents, warranty cards, "
        "utility bills, appliance manuals, insurance policies, and tenancy agreements. "
        "Be friendly and explain things in plain language. "
        "Ground all answers in the provided documents."
    ),
    terminology={"workspace": "Home workspace", "document": "Home document",
                 "query": "Ask about your home", "user_label": "Homeowner / Tenant"},
    patterns=[
        (r'(?:warranty|guarantee)[\s:]+\d+\s*(?:year|month)', "warranty period"),
        (r'(?:rent|mortgage)[\s:]+(?:Rs\.?|₹|\$|£)[\d,]+',   "payment amount"),
        (r'(?:due date|payment date)[\s:]+\S+',                "due date"),
        (r'(?:policy\s+no|policy\s+number)[\s:]+\w+',         "policy number"),
        (r'(?:model|serial)\s+(?:no|number)?[\s:]+\w+',       "model/serial"),
        (r'(?:sq\.?\s*ft|sq\.?\s*m)',                          "area"),
        (r'(?:electricity|water|gas)\s+bill[\s:]+[\d,]+',     "utility bill"),
        (r'(?:contact|helpline|support)[\s:]+[\d\s\-\+]+',    "contact number"),
    ],
    suggestions=[
        "What is the warranty period for this appliance?",
        "When is the next rent payment due?",
        "Summarise the insurance coverage",
        "What are the terms of the tenancy?",
        "How do I claim warranty?",
        "What maintenance is required?",
    ],
)

IT = SectorConfig(
    id="it", label="IT", accent="blue",
    persona=(
        "You are a senior software engineer and technical documentation analyst. "
        "Help developers, architects, and IT managers extract information from "
        "API docs, system design documents, SLAs, incident reports, and security policies. "
        "Be precise, use technical terminology correctly. "
        "Ground all answers strictly in the provided documents."
    ),
    terminology={"workspace": "Project workspace", "document": "Tech document",
                 "query": "Query your tech docs", "user_label": "Developer / Architect"},
    patterns=[
        (r'(?:version|v)\s*\d+(?:\.\d+){1,3}',              "version number"),
        (r'https?://[^\s<>"]+',                               "URL/endpoint"),
        (r'(?:SLA|uptime)[\s:]+[\d.]+\s*%',                  "SLA/uptime"),
        (r'(?:latency|response time)[\s:]+\d+\s*ms',         "latency"),
        (r'(?:port|PORT)[\s:]+\d{2,5}',                      "port number"),
        (r'(?:CPU|RAM|memory)[\s:]+\d+\s*(?:GB|MB|cores?)',  "resource spec"),
        (r'(?:error|status)\s+code[\s:]+\d{3}',              "status code"),
        (r'(?:CVE)-\d{4}-\d+',                               "CVE reference"),
    ],
    suggestions=[
        "What are the API rate limits?",
        "Summarise the system architecture",
        "What are the SLA requirements?",
        "What security vulnerabilities are documented?",
        "Compare API versions across documents",
        "What are the deployment prerequisites?",
    ],
)

ALL_SECTORS: Dict[str, SectorConfig] = {
    s.id: s for s in [AGRICULTURE, HEALTHCARE, EDUCATION, MILITARY, HOUSEHOLD, IT]
}
DEFAULT_SECTOR = "it"


def get_sector(sector_id: str) -> SectorConfig:
    return ALL_SECTORS.get(sector_id, ALL_SECTORS[DEFAULT_SECTOR])


def list_sectors() -> list:
    return [{"id": s.id, "label": s.label, "accent": s.accent}
            for s in ALL_SECTORS.values()]
