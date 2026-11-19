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
]

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
    }
]

def ocisti_tekst(tekst):
    return re.sub(r'\s+', ' ', tekst).strip()

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

def izvuci_srz_subvencije(naslov, izvor_skraceno, pun_link):
    n = naslov.lower()
    pronadjeno = pronadji_brojeve_u_tekstu(naslov)

    if not pronadjeno and pun_link.startswith("http") and not pun_link.lower().endswith(".pdf"):
        try:
            r = requests.get(pun_link, headers=HEADERS, timeout=12, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            s = BeautifulSoup(r.text, "html.parser")
            glavni = s.find("main") or s.find("article") or s.body
            if glavni:
                tekst_stranice = ocisti_tekst(glavni.get_text())[:4000]
                pronadjeno = pronadji_brojeve_u_tekstu(tekst_stranice)
        except Exception:
            pass

    if pronadjeno:
        return " | ".join(pronadjeno)

    if "самозапошљавањ" in n or "samozaposljavanj" in n:
        return "једнократна субвенција за старт"
    if "запошљавањ" in n or "zaposljavanj" in n:
        return "субвенција / повраћај пореза и доприноса"
    if "опрем" in n or "oprem" in n:
        return "бесповратна средства + повољан кредит"
    if "старт" in n or "start" in n or "почетни" in n or "pocetni" in n:
        return "старт-ап грант / повољан кредит"
    if izvor_skraceno == "Град Београд":
        return "градска субвенција за привреду"

    return "детаљи и износи у тексту позива"

def generisi_detaljnu_razradu(naslov, izvor_skraceno):
    n = naslov.lower()
    
    if "самозапошљавањ" in n or "samozaposljavanj" in n:
        return (
            "<strong>🎯 ДЕТАЉАН ВОДИЧ: Самозапошљавање (НСЗ)</strong><br>"
            "• <strong>1. Услови за пријаву:</strong> Незапослено лице на евиденцији НСЗ, претходно завршена законска обука за развој предузетништва.<br>"
            "• <strong>2. Потребна документација и обрасци:</strong><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Званичан захтев са бизнис планом (преузима се са сајта НСЗ у форми формулара).<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Доказ о завршеној обуци.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Уверење из Пореске управе да су измирене пореске обавезе.<br>"
            "• <strong>3. Административни кораци:</strong> Подношење комплетне документације филијали НСЗ у предвиђеном року, израда пројекције пословања за прву годину.<br>"
            "• <strong>4. Главне обавезе након одобравања:</strong> Регистрација радње (паушал или књигаш) у АПР-у, потписивање уговора са НСЗ, обавеза рада и уплате доприноса минимум 12 месеци."
        )
    elif "опрем" in n or "oprem" in n:
        return (
            "<strong>🎯 ДЕТАЉАН ВОДИЧ: Набавка опреме и машина</strong><br>"
            "• <strong>1. Облик подршке:</strong> Комбинација бесповратних средстава (грант) и повољног кредита.<br>"
            "• <strong>2. Обавезна документација и обрасци:</strong><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Инвестициони програм / Бизнис план по прописаној шеми Фонда за развој.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Профактура добављача опреме са детаљном техничком спецификацијом.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Финансијски извештаји за претходне године (за постојеће фирме).<br>"
            "• <strong>3. Средства обезбеђења:</strong> Менице, хипотека или банкарска гаранција у зависности од висине траженог
