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
    "јавни позив", "javni poziv",
    "конкурс", "konkurs"
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

def odgovara_kljucnim_recima(naslov):
    n = naslov.lower()
    if len(n) < 15 or len(n) > 250:
        return False
    return any(rec in n for rec in KLJUCNE_RECI)

def generisi_ciljane_detalje(naslov, izvor_skraceno):
    n = naslov.lower()
    
    if "самозапошљавањ" in n or "samozaposljavanj" in n:
        return (
            "<strong>Програм:</strong> Самозапошљавање (НСЗ)<br>"
            "<strong>Ко има право:</strong> Незапослена лица на евиденцији НСЗ која су завршила обуку за развој предузетништва.<br>"
            "<strong>Облик подршке:</strong> Једнократна бесповратна средства за покретање бизниса (паушалци или књигаши).<br>"
            "<strong>Главна обавеза:</strong> Редовно обављање делатности и плаћање пореза и доприноса минимум 12 месеци."
        )
    elif "опрем" in n or "oprem" in n:
        return (
            "<strong>Програм:</strong> Суфинансирање набавке опреме и машина<br>"
            "<strong>Облик подршке:</strong> Комбинација бесповратних средстава (гранта) и повољног кредита.<br>"
            "<strong>Документација:</strong> Обавезна профактура добављача опреме и бізнис план / инвестициони програм."
        )
    elif "старт" in n or "start" in n or "почетни" in n or "pocetni" in n:
        return (
            "<strong>Програм:</strong> Подршка почетницима у пословању (Старт-ап)<br>"
            "<strong>Ко има право:</strong> Предузетници и привредна друштва регистровани у кратком периоду (најчешће до 2 године).<br>"
            "<strong>Погодности:</strong> Повољни услови кредитирања уз грејс период и део бесповратних средстава."
        )
    elif "запошљавањ" in n or "zaposljavanj" in n:
        return (
            "<strong>Програм:</strong> Субвенције за запошљавање нових радника<br>"
            "<strong>Услови за послодавца:</strong> Исплата зараде у складу са законом, задржавање радног односа одређени период (обично 12+ месеци) и несмањивање укупног броја запослених."
        )
    elif izvor_skraceno == "Град Београд":
        return (
            "<strong>Извор:</strong> Град Београд - Секретаријат за привреду<br>"
            "<strong>Услови:</strong> Седиште привредног субјекта на територији града Београда, измирене пореске обавезе према држави и локалној самоуправи."
        )
    else:
        return (
            f"<strong>Извор подршке:</strong> {izvor_skraceno}<br>"
            "<strong>Напомена:</strong> Овај јавни позив циља привредне субјекте. Препорука је да се отвори званични документ са линка ради провере тачних рокова, износа и услова за паушалце."
        )

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
    postojeci_linkovi = {s["link"]: s for s in baza.get("konkursi", [])}
    
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
                naslov = ocisti_tekst(a.get_text())
                href = a["href"].strip()

                if not odgovara_kljucnim_recima(naslov):
                    continue

                if href.startswith("/"):
                    pun_link = izvor["baza_url"].rstrip("/") + href
                elif href.startswith("http"):
                    pun_link = href
                else:
                    continue

                if pun_link.rstrip("/") == izvor["url"].rstrip("/"):
                    continue

                if pun_link not in postojeci_linkovi:
                    detalji = generisi_ciljane_detalje(naslov, izvor["skraceno"])
                    postojeci_linkovi[pun_link] = {
                        "naslov": naslov,
                        "izvor": izvor["skraceno"],
                        "izvor_pun": izvor["naziv"],
                        "link": pun_link,
                        "datum_pronalaska": danas,
                        "detalji": detalji
                    }
                    pronadjeno_za_izvor += 1

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
