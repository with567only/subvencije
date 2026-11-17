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

def izvuci_tekst_sa_stranice(url):
    """Улази на линк конкурса и покушава да извуче сажетак текста са странице."""
    if url.lower().endswith(".pdf"):
        return "Документ је у PDF формату. Потребно је преузети званични текст конкурса са линка изнад."
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, verify=False)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Уклањамо меније, футере и скрипте да не купе ђубре
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
            
        paragrafi = [ocisti_tekst(p.get_text()) for p in soup.find_all("p") if len(ocisti_tekst(p.get_text())) > 60]
        if paragrafi:
            sazetak = " ".join(paragrafi[:3])
            if len(sazetak) > 450:
                sazetak = sazetak[:447] + "..."
            return sazetak
    except Exception:
        pass
    return ""

def generisi_pametne_detalje(naslov, izvor_skraceno, link):
    """Комбинује извучени текст са странице и паметну категоризацију услова."""
    n = naslov.lower()
    izvuceno = izvuci_tekst_sa_stranice(link)
    
    # Аутоматско препознавање типа конкурса и додавање смерница
    if "самозапошљавањ" in n or "samozaposljavanj" in n:
        tip = "<strong>Тип подршке:</strong> Бесповратна средства за покретање сопственог бизниса (НСЗ).<br><strong>Кључни услови:</strong> Евиденција незапослених НСЗ, завршена обука за предузетништво, обавеза обављања делатности мин. 12 месеци и плаћања доприноса."
    elif "опрем" in n or "oprem" in n or "инвестиц" in n or "investic" in n:
        tip = "<strong>Тип подршке:</strong> Суфинансирање набавке нове или половне опреме и машина.<br><strong>Кључни услови:</strong> Најчешће 20-30% бесповратних средстава, остатак повољан кредит или сопствено учешће. Потребна профактура добављача."
    elif "старт" in n or "start" in n or "почетни" in n or "pocetni" in n:
        tip = "<strong>Тип подршке:</strong> Програм за почетнике у пословању (фирме млађе од 2 године).<br><strong>Кључни услови:</strong> Обавезан бизнис план, део средстава је бесповратан (до 30-40%), без хипотеке за мање износе уз јемство или менице."
    elif "запошљавањ" in n or "zaposljavanj" in n or "теже запошљив" in n:
        tip = "<strong>Тип подршке:</strong> Субвенција послодавцима за отварање нових радних места.<br><strong>Кључни услови:</strong> Послодавац не сме смањивати број запослених у претходном периоду и мора задржати радника у радном односу одређени период."
    elif izvor_skraceno == "Град Београд":
        tip = "<strong>Тип подршке:</strong> Градски подстицаји за микро и мала предузећа и предузетнике на територији Београда.<br><strong>Кључни услови:</strong> Седиште фирме у Београду, измирени локални и републички порези."
    else:
        tip = "<strong>Тип подршке:</strong> Јавни позив / конкурс за привредне субјекте.<br><strong>Напомена:</strong> Проверити у званичном тексту да ли обухвата паушалце или само предузетнике књигаше и ДОО."

    rezultat = tip
    if izvuceno:
        rezultat += f"<br><br><strong>Извод са странице конкурса:</strong><br><em>{izvuceno}</em>"
    
    return rezultat

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

                # Ако је конкурс нов или ако стари нема попуњене детаље -> генериши их аутоматски!
                if pun_link not in postojeci_linkovi or not postojeci_linkovi[pun_link].get("detalji"):
                    detalji = generisi_pametne_detalje(naslov, izvor["skraceno"], pun_link)
                    postojeci_linkovi[pun_link] = {
                        "naslov": naslov,
                        "izvor": izvor["skraceno"],
                        "izvor_pun": izvor["naziv"],
                        "link": pun_link,
                        "datum_pronalaska": postojeci_linkovi.get(pun_link, {}).get("datum_pronalaska", danas),
                        "detalji": detalji
                    }
                    pronadjeno_za_izvor += 1

            status_izvora[izvor["skraceno"]] = f"ОК (ажурирано: {pronadjeno_za_izvor})"
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
