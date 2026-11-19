import json
import os
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

KLJUCNE_RECI = [
    "предузетни", "preduzetni",
    "паушал", "pausal",
    "опрем", "oprem",
    "запошљавањ", "zaposljavanj",
    "самозапошљавањ", "samozaposljavanj",
    "субвенциј", "subvencij",
    "микро", "mikro",
    "мала предузећа", "mala preduzeca",
    "старт", "start",
    "бесповратн", "bespovratn",
    "привред", "privred"
]

PU_MF_KLJUCNE_RECI = [
    "олакшиц", "olaksic",
    "порез", "porez",
    "допринос", "doprinos",
    "паушал", "pausal",
    "предузетни", "preduzetni",
    "подстицај", "podsticaj",
    "субвенциј", "subvencij",
    "бесповратн", "bespovratn",
    "фискал", "fiskal",
    "привред", "privred",
    "запошљавањ", "zaposljavanj"
]

PONISTENJE_RECI = [
    "ponistenje", "поништење",
    "ponisten", "поништен",
    "ponistava", "поништава"
]

ZABRANJENE_RECI = [
    "списак кандидата", "spisak kandidata",
    "стипендиј", "stipendij",
    "службеника", "sluzbenika",
    "изборним радњама", "izbornim radnjama",
    "радног места", "radnog mesta",
    "радних места", "radnih mesta",
    "ученицима", "ucenicima",
    "студентима", "studentima",
    "испит", "ispit",
    "агенције за запошљавање", "agencije za zaposljavanje",
    "намештеника", "namestenika",
    "сектор за", "sektor za",
    "одељење за", "odeljenje za",
    "управа за", "uprava za",
    "организациона структура", "organizacionalna struktura",
    "надлежности", "nadleznosti",
    "контакти", "kontakti"
] + PONISTENJE_RECI

OBRAZAC_NASTAVCI = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar")
OBRAZAC_KLJUCNE_RECI = [
    "образац", "obrazac",
    "формулар", "formular",
    "захтев", "zahtev",
    "бизнис план", "biznis plan",
    "инвестициони програм", "investicioni program",
    "упутство за пријав", "uputstvo za prijav",
    "пријавни лист", "prijavni list"
]
ZABRANJENI_OBRASCI_RECI = [
    "сервисни центар", "11011",
    "музички програм", "филмски", "позоришни",
    "уметнички програм", "дечји програм",
    "пореске пријаве и захтеви",
    "контакти", "надлежности", "о нама"
] + PONISTENJE_RECI

IZVORI = [
    {
        "naziv": "Национална служба за запошљавање (НСЗ)",
        "skraceno": "НСЗ",
        "url": "https://www.nsz.gov.rs/sadrzaj/konkursi-nsz/11",
        "baza_url": "https://www.nsz.gov.rs"
    },
    {
        "naziv": "Фонд за развој РС",
        "skraceno": "Фонд за развој",
        "url": "https://fondzarazvoj.co.rs/lat/proizvodi/bespovratna-sredstva",
        "baza_url": "https://fondzarazvoj.co.rs"
    },
    {
        "naziv": "Град Београд - Огласи и конкурси",
        "skraceno": "Град Београд",
        "url": "https://www.beograd.rs/cir/gradski-oglasi-i-konkursi/",
        "baza_url": "https://www.beograd.rs"
    },
    {
        "naziv": "Министарство привреде",
        "skraceno": "Министарство привреде",
        "url": "https://privreda.gov.rs/javni-pozivi",
        "baza_url": "https://privreda.gov.rs"
    },
    {
        "naziv": "Пореска управа Републике Србије",
        "skraceno": "Пореска управа",
        "url": "https://www.purs.gov.rs/aktuelnosti/vesti.html",
        "baza_url": "https://www.purs.gov.rs"
    },
    {
        "naziv": "Министарство финансија РС",
        "skraceno": "Министарство финансија",
        "url": "https://www.mfin.gov.rs/aktivnosti/vesti",
        "baza_url": "https://www.mfin.gov.rs"
    }
]

def ocisti_tekst(tekst):
    return re.sub(r'\s+', ' ', tekst).strip()

def napravi_pun_link(href, baza_url):
    href = (href or "").strip()
    if not href or href.startswith("#") or href.lower().startswith("javascript:") or href.lower().startswith("mailto:"):
        return ""
    if href.startswith("/"):
        return baza_url.rstrip("/") + href
    if href.startswith("http"):
        return href
    return baza_url.rstrip("/") + "/" + href.lstrip("/")

def sadrzi_ponistenje(tekst):
    t = (tekst or "").lower()
    return any(p in t for p in PONISTENJE_RECI)

def odgovara_kljucnim_recima(naslov, izvor_skraceno=""):
    n = naslov.lower()
    if len(n) < 15 or len(n) > 250:
        return False
    if any(zabr in n for zabr in ZABRANJENE_RECI):
        return False
    if izvor_skraceno == "Град Београд":
        usko_privreda = [
            "привред", "privred", "предузетни", "preduzetni",
            "субвенциј", "subvencij", "бесповратн", "bespovratn",
            "пољопривред", "poljoprivred", "иновациј", "inovacij",
            "туризм", "turizm", "занат", "zanat"
        ]
        return any(rec in n for rec in usko_privreda)
    if izvor_skraceno in ("Пореска управа", "Министарство финансија"):
        return any(rec in n for rec in PU_MF_KLJUCNE_RECI)
    return any(rec in n for rec in KLJUCNE_RECI)

def pronadji_brojeve_u_tekstu(tekst):
    pronadjeno = []
    procenti = re.findall(r'\b\d{1,3}(?:[.,]\d+)?\s*%', tekst)
    iznosi_rsd = re.findall(
        r'(?:до\s+|од\s+|износи\s+)?\d{1,3}(?:[.,\s]\d{3})+\s*(?:рсд|rsd|динара|дин\.)',
        tekst,
        flags=re.IGNORECASE
    )
    iznosi_eur = re.findall(
        r'(?:до\s+|од\s+)?\d{1,3}(?:[.,\s]\d{3})*\s*(?:евра|еур|eur|€)',
        tekst,
        flags=re.IGNORECASE
    )

    for p in procenti:
        cisto = re.sub(r'\s+', '', p)
        if cisto not in pronadjeno:
            pronadjeno.append(cisto)
    for i in iznosi_rsd + iznosi_eur:
        cisto = re.sub(r'\s+', ' ', i).strip()
        if cisto not in pronadjeno:
            pronadjeno.append(cisto)

    return pronadjeno[:4]

def izvuci_rokove_i_datume(naslov, soup_stranice=None):
    datumi_u_naslovu = re.findall(r'\b\d{1,2}\.\d{1,2}\.\d{4}\.?', naslov or "")
    cisti_naslov_datumi = []
    for d in datumi_u_naslovu:
        d_cist = d.rstrip(".") + "."
        if d_cist not in cisti_naslov_datumi:
            cisti_naslov_datumi.append(d_cist)

    tekst_stranice = ""
    if soup_stranice is not None:
        glavni = soup_stranice.find("main") or soup_stranice.find("article") or soup_stranice.body
        if glavni:
            tekst_stranice = ocisti_tekst(glavni.get_text())[:6000]

    rok_mecevi = []
    if tekst_stranice:
        for m in re.finditer(
            r'(?:рок\s+(?:за\s+(?:подношење|пријав)[^.:\n]{0,45}|је\s+до\s+|до\s+)|отворен\s+до\s+|траје\s+до\s+|пријаве\s+до\s+|завршава\s+(?:се\s+)?до\s+)(\d{1,2}\.\d{1,2}\.\d{4}\.?)',
            tekst_stranice,
            flags=re.IGNORECASE
        ):
            dat = m.group(1).rstrip(".") + "."
            if dat not in rok_mecevi:
                rok_mecevi.append(dat)

    if rok_mecevi and cisti_naslov_datumi:
        return f"Објављено: {cisti_naslov_datumi[0]} | Траје до: {rok_mecevi[0]}"
    if rok_mecevi:
        return f"Траје до: {' / '.join(rok_mecevi[:2])}"
    if cisti_naslov_datumi:
        return f"Објављено: {' / '.join(cisti_naslov_datumi[:2])} (рок није наведен)"

    return "Рок није наведен у позиву"

def izvuci_srz_subvencije(naslov, izvor_skraceno, pun_link, soup_stranice=None):
    n = naslov.lower()
    pronadjeno = pronadji_brojeve_u_tekstu(naslov)

    if not pronadjeno and soup_stranice is not None:
        glavni = soup_stranice.find("main") or soup_stranice.find("article") or soup_stranice.body
        if glavni:
            tekst_stranice = ocisti_tekst(glavni.get_text())[:4000]
            pronadjeno = pronadji_brojeve_u_tekstu(tekst_stranice)

    if pronadjeno:
        return " | ".join(pronadjeno)

    if "самозапошљавањ" in n or "samozaposljavanj" in n:
        return "једнократна субвенција за старт"
    if "запошљавањ" in n or "zaposljavanj" in n:
        return "субвенција / повраћај пореза и доприноса"
    if "опрем" in n or "oprem" in n:
        return "бесповратна средства + повољан кредит"
    if "старт" in n or "start" in n or "почетни" in n
