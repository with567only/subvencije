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

def generisi_detaljnu_razradu(naslov, izvor_skraceno):
    n = naslov.lower()
    
    if "самозапошљавањ" in n or "samozaposljavanj" in n:
        return (
            "<strong>📌 ПРОГРАМ: Самозапошљавање (НСЗ)</strong><br>"
            "• <strong>Ко има право:</strong> Незапослена лица на евиденцији НСЗ која су завршила званичну обуку за развој предузетништва.<br>"
            "• <strong>Облик и висина подршке:</strong> Једнократна бесповратна средства (фиксни износ по позиву, намењен за оснивање радње — паушал или књигаш).<br>"
            "• <strong>Кључне обавезе:</strong> Обавеза обављања регистроване делатности и уплате доприноса минимум 12 месеци; забрана отуђења опреме купљене средствима.<br>"
            "• <strong>Потребна документација:</strong> Бизнис план са пројекцијом, лична карта, уверење из Пореске управе да нема дуговања."
        )
    elif "опрем" in n or "oprem" in n:
        return (
            "<strong>📌 ПРОГРАМ: Набавка опреме и машина</strong><br>"
            "• <strong>Облик подршке:</strong> Комбинација бесповратних средстава (грант до 20-30%) и повољног кредита Фонда за развој или пословних банака.<br>"
            "• <strong>Услови:</strong> Фирма мора бити регитована раније (није за апсолутне почетнике осим ако је посебан старт-ап програм), са уредним пословним извештајима.<br>"
            "• <strong>Документација:</strong> Профактура добављача опреме, биланси за претходну годину, бизнис/инвестициони план."
        )
    elif "старт" in n or "start" in n or "почетни" in n or "pocetni" in n:
        return (
            "<strong>📌 ПРОГРАМ: Подршка почетницима у пословању (Старт-ап)</strong><br>"
            "• <strong>Ко има право:</strong> Предузетници и привредна друштва регистровани у кратком периоду (обично мање од 2 године од дана подношења захтева).<br>"
            "• <strong>Погодности:</strong> Повољни кредити уз грејс период и део бесповратних средстава за развој почетног бизниса.<br>"
            "• <strong>Услови:</strong> Доказана одрживост бизнис плана, обезбеђење у виду меница или друге врсте колатерала."
        )
    elif "запошљавањ" in n or "zaposljavanj" in n:
        return (
            "<strong>📌 ПРОГРАМ: Субвенције за запошљавање нових радника</strong><br>"
            "• <strong>Право коришћења:</strong> Послодавци (предузетници и фирме) који запошљавају лица из категорија теже запошљивих.<br>"
            "• <strong>Обавезе послодавца:</strong> Редовна исплата зарада, задржавање радника у радном односу минимално 12 месеци (или дуже према пропозицијама позива), и несмањивање укупног броја запослених у претходном периоду."
        )
    elif izvor_skraceno == "Град Београд":
        return (
            "<strong>📌 ИЗВОР: Град Београд (Секретаријат за привреду)</strong><br>"
            "• <strong>Општи услов:</strong> Седиште привредног субјекта мора бити на територији града Београда.<br>"
            "• <strong>Фискална дисциплина:</strong> Измирене све пореске обавезе према Републици и Граду.<br>"
            "• <strong>Напомена:</strong> Пратити наменске конкурсе за женско предузетништво, стари занатске делатности или развој микро бизниса."
        )
    else:
        return (
            f"<strong>📌 ЈАВНИ ПОЗИВ — {izvor_skraceno}</strong><br>"
            "• <strong>Препорука:</strong> Овај конкурс захтева детаљну анализу званичне конкурсне документације.<br>"
            "• <strong>Основне пропедеутике:</strong> Проверити да ли обухвата паушалце, рокове за пријаву и тачке везане за документацију преко е-Управе / Портала пореске управе."
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
                    detalji = generisi_detaljnu_razradu(naslov, izvor["skraceno"])
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
