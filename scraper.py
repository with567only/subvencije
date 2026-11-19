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
    if "старт" in n or "start" in n or "почетни" in n or "pocetni" in n:
        return "старт-ап грант / повољан кредит"
    if izvor_skraceno == "Град Београд":
        return "градска субвенција за привреду"

    return "детаљи и износи у тексту позива"

def izvuci_obrasce_sa_stranice(soup_stranice, baza_url, izvor_url):
    obrasci = []
    vidjeni_url = set()

    if soup_stranice is None:
        return obrasci

    glavni = soup_stranice.find("main") or soup_stranice.find("article") or soup_stranice.body or soup_stranice

    for a in glavni.find_all("a", href=True):
        if a.find_parent(["nav", "header", "footer"]):
            continue

        pun_url = napravi_pun_link(a["href"], baza_url)
        if not pun_url or pun_url in vidjeni_url:
            continue
        if pun_url.rstrip("/") == izvor_url.rstrip("/"):
            continue

        tekst_linka = ocisti_tekst(a.get_text())
        donji_url = pun_url.lower()
        donji_tekst = tekst_linka.lower()

        if any(z in donji_tekst or z in donji_url for z in ZABRANJENI_OBRASCI_RECI):
            continue

        je_fajl = donji_url.endswith(OBRAZAC_NASTAVCI)
        je_obrazac_po_kljucu = any(k in donji_url or k in donji_tekst for k in OBRAZAC_KLJUCNE_RECI)

        if je_fajl or je_obrazac_po_kljucu:
            vidjeni_url.add(pun_url)
            naziv_obrasca = tekst_linka if len(tekst_linka) >= 4 else pun_url.split("/")[-1] or "Образац / документ"
            if len(naziv_obrasca) > 120:
                naziv_obrasca = naziv_obrasca[:117] + "..."
            obrasci.append({
                "naziv": naziv_obrasca,
                "url": pun_url
            })

        if len(obrasci) >= 6:
            break

    return obrasci

def generisi_detaljnu_razradu(naslov, izvor_skraceno):
    n = naslov.lower()

    if "самозапошљавањ" in n or "samozaposljavanj" in n:
        stavke = [
            "<strong>ДЕТАЉАН ВОДИЧ: Самозапошљавање (НСЗ)</strong>",
            "- <strong>1. Услови:</strong> Евиденција у НСЗ и завршена обука за предузетништво.",
            "- <strong>2. Обрасци и докази:</strong> Захтев са бизнис планом, доказ о обуци, пореско уверење.",
            "- <strong>3. Кораци:</strong> Предаја документације филијали НСЗ у року и план за прву годину.",
            "- <strong>4. Обавезе:</strong> Регистрација у АПР-у, уговор са НСЗ и рад/доприноси минимум 12 месеци.",
            "- <strong>5. Попуњавање:</strong> Ускладити шифру делатности, реалне трошкове и први приход; проверити порески дуг."
        ]
    elif "опрем" in n or "oprem" in n:
        stavke = [
            "<strong>ДЕТАЉАН ВОДИЧ: Набавка опреме и машина</strong>",
            "- <strong>1. Подршка:</strong> Комбинација бесповратних средстава (грант) и повољног кредита.",
            "- <strong>2. Обрасци и прилози:</strong> Инвестициони програм/бизнис план, профактуре, финансијски извештаји.",
            "- <strong>3. Обезбеђење:</strong> Менице, хипотека или банкарска гаранција према висини износа.",
            "- <strong>4. Попуњавање:</strong> Тачан ПИБ, МБ и шифра делатности; износи у програму морају пратити профактуре."
        ]
    elif "старт" in n or "start" in n or "почетни" in n or "pocetni" in n:
        stavke = [
            "<strong>ДЕТАЉАН ВОДИЧ: Подршка почетницима (Старт-ап)</strong>",
            "- <strong>1. Корисници:</strong> Предузетници и привредна друштва са кратком историјом пословања.",
            "- <strong>2. Документација:</strong> Захтев за кредитирање, бизнис план, доказ о простору (власништво/закуп).",
            "- <strong>3. Попуњавање:</strong> Раздвојити сопствено учешће и тражена средства; ускладити адресу и простор."
        ]
    elif "запошљавањ" in n or "zaposljavanj" in n:
        stavke = [
            "<strong>ДЕТАЉАН ВОДИЧ: Субвенције за запошљавање</strong>",
            "- <strong>1. Услови:</strong> Редовне зараде и задржавање новозапосленог на истом месту најмање 12 месеци.",
            "- <strong>2. Документација:</strong> Захтев, CROSO потврда о броју запослених, доказ о измиреним порезима.",
            "- <strong>3. Попуњавање:</strong> Проверити стање на CROSO пре предаје и уписати тачне податке о радном месту."
        ]
    elif izvor_skraceno == "Град Београд":
        stavke = [
            "<strong>ДЕТАЉАН ВОДИЧ: Град Београд</strong>",
            "- <strong>1. Услов:</strong> Седиште привредног субјекта на територији београдских општина.",
            "- <strong>2. Документација:</strong> Образац пријаве, извод из АПР-а, потврда Пореске управе.",
            "- <strong>3. Попуњавање:</strong> Попунити сва обавезна поља, ускладити ПИБ и адресу са АПР-ом и пратити рокове."
        ]
    else:
        stavke = [
            f"<strong>ДЕТАЉАН ВОДИЧ — {izvor_skraceno}</strong>",
            "- <strong>1. Провера:</strong> Прочитати текст јавног позива са званичног линка и проверити рок.",
            "- <strong>2. Документација:</strong> Решење/извод АПР-а, потврда НБС о неблокираности, пореско уверење.",
            "- <strong>3. Попуњавање:</strong> Ускладити ПИБ, МБ, шифру делатности и предрачуне са условима позива."
        ]

    return "<br>".join(stavke)

def ucitaj_postojece():
    if os.path.exists("podaci.json"):
        try:
            with open("podaci.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"poslednje_azuriranje": "", "konkursi": [], "status_izvora": {}}

def pokreni_pretragu():
    baza = ucitaj_postojece()
    postojeci_linkovi = {}
    for s in baza.get("konkursi", []):
        link_s = s.get("link", "")
        naslov_s = s.get("naslov", "")
        if sadrzi_ponistenje(naslov_s) or sadrzi_ponistenje(link_s):
            continue
        if odgovara_kljucnim_recima(naslov_s, s.get("izvor", "")):
            ocisceni_obrasci = [
                o for o in (s.get("obrasci") or [])
                if not sadrzi_ponistenje(o.get("naziv", "")) and not sadrzi_ponistenje(o.get("url", ""))
            ]
            s["obrasci"] = ocisceni_obrasci
            postojeci_linkovi[link_s] = s

    danas = datetime.now().strftime("%Y-%m-%d")
    vreme_sada = datetime.now().strftime("%d.%m.%Y. у %H:%M")
    status_izvora = {}

    for izvor in IZVORI:
        pronadjeno_za_izvor = 0
        try:
            odgovor = requests.get(izvor["url"], headers=HEADERS, timeout=25, verify=False)
            odgovor.encoding = odgovor.apparent_encoding or "utf-8"
            soup = BeautifulSoup(odgovor.text, "html.parser")

            for a in soup.find_all("a", href=True):
                if a.find_parent(["nav", "header", "footer"]):
                    continue

                naslov = ocisti_tekst(a.get_text())
                if not odgovara_kljucnim_recima(naslov, izvor["skraceno"]):
                    continue

                pun_link = napravi_pun_link(a["href"], izvor["baza_url"])
                if not pun_link or pun_link.rstrip("/") == izvor["url"].rstrip("/"):
                    continue
                if sadrzi_ponistenje(naslov) or sadrzi_ponistenje(pun_link):
                    continue

                soup_stranice = None
                if pun_link.startswith("http") and not pun_link.lower().endswith(OBRAZAC_NASTAVCI):
                    try:
                        r_pod = requests.get(pun_link, headers=HEADERS, timeout=12, verify=False)
                        r_pod.encoding = r_pod.apparent_encoding or "utf-8"
                        soup_stranice = BeautifulSoup(r_pod.text, "html.parser")
                    except Exception:
                        soup_stranice = None

                srz = izvuci_srz_subvencije(naslov, izvor["skraceno"], pun_link, soup_stranice)
                rokovi = izvuci_rokove_i_datume(naslov, soup_stranice)
                obrasci = izvuci_obrasce_sa_stranice(soup_stranice, izvor["baza_url"], pun_link)
                detalji = generisi_detaljnu_razradu(naslov, izvor["skraceno"])

                if pun_link not in postojeci_linkovi:
                    postojeci_linkovi[pun_link] = {
                        "naslov": naslov,
                        "srz_subvencije": srz,
                        "rokovi": rokovi,
                        "izvor": izvor["skraceno"],
                        "izvor_pun": izvor["naziv"],
                        "link": pun_link,
                        "datum_pronalaska": danas,
                        "detalji": detalji,
                        "obrasci": obrasci
                    }
                    pronadjeno_za_izvor += 1
                else:
                    postojeci_linkovi[pun_link]["srz_subvencije"] = srz
                    postojeci_linkovi[pun_link]["rokovi"] = rokovi
                    postojeci_linkovi[pun_link]["detalji"] = detalji
                    postojeci_linkovi[pun_link]["obrasci"] = obrasci

            status_izvora[izvor["skraceno"]] = f"ОК (нових: {pronadjeno_za_izvor})"
        except Exception as e:
            status_izvora[izvor["skraceno"]] = f"Грешка ({type(e).__name__})"

    svi_konkursi = sorted(
        postojeci_linkovi.values(),
        key=lambda x: x.get("datum_pronalaska", "2000-01-01"),
        reverse=True
    )

    rezultat = {
        "poslednje_azuriranje": vreme_sada,
        "status_izvora": status_izvora,
        "konkursi": svi_konkursi[:150]
    }

    with open("podaci.json", "w", encoding="utf-8") as f:
        json.dump(rezultat, f, ensure_ascii=False, indent=2)

    print("Ажурирање завршено:", vreme_sada)

if __name__ == "__main__":
    pokreni_pretragu()
