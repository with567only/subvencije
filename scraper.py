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
            "• <strong>3. Средства обезбеђења:</strong> Менице, хипотека или банкарска гаранција у зависности од висине траженог износа кредита/гранта."
        )
    elif "старт" in n or "start" in n or "почетни" in n or "pocetni" in n:
        return (
            "<strong>🎯 ДЕТАЉАН ВОДИЧ: Подршка почетницима (Старт-ап)</strong><br>"
            "• <strong>1. Циљна група:</strong> Предузетници и привредна друштва са кратком историјом пословања (обично до 2 године од дана оснивања).<br>"
            "• <strong>2. Потребни обрасци и прилози:</strong><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Захтев за кредитирање почетника.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Бизнис план са тржишном анализом и пројекцијом прихода.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Докази о власништву или закупу пословног простора."
        )
    elif "запошљавањ" in n or "zaposljavanj" in n:
        return (
            "<strong>🎯 ДЕТАЉАН ВОДИЧ: Субвенције за запошљавање нових радника</strong><br>"
            "• <strong>1. Услови за послодавца:</strong> Редовна исплата зарада, задржавање новозапосленог лица на истом радном месту најмање 12 месеци.<br>"
            "• <strong>2. Потребна документација:</strong><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Захтев за доделу субвенције за запошљавање.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Потврда Централног регистра обавезног социјалног осигурања (CROSO) о броју запослених.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Доказ да послодавац нема неизмирених обавеза по основу пореза и доприноса."
        )
    elif izvor_skraceno == "Град Београд":
        return (
            "<strong>🎯 ДЕТАЉАН ВОДИЧ: Град Београд (Секретаријат за привреду)</strong><br>"
            "• <strong>1. Територијални услов:</strong> Седиште привредног субјекта искључиво на територији београдских општина.<br>"
            "• <strong>2. Документација:</strong><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Образац пријаве на јавни конкурс Града Београда.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Извод из АПР-а (важећи статус).<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;- Потврда Пореске управе о измиреним пореским обавезама."
        )
    else:
        return (
            f"<strong>🎯 ДЕТАЉАН ВОДИЧ — {izvor_skraceno}</strong><br>"
            "• <strong>1. Провера административних услова:</strong> Обавезно преузети званични конкурс са линка и проверити рок за подношење пријава.<br>"
            "• <strong>2. Стандардни сет докумената:</strong> Решење из АПР-а, потврда Народне банке (НБС) да рачун није у блокади, уверење из Пореске управе."
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
