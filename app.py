# app.py
import random
import csv
import io
import urllib.parse
import streamlit as st

# --- Beállítások / adatok (kérésed szerint) ---
PARTICIPANTS = ["Dóri", "Máté", "Bence", "Gréti", "Anya", "Csenge", "Geri"]
COUPLES = [("Dóri", "Máté"), ("Bence", "Gréti"), ("Csenge", "Geri")]  # ők nem húzhatják egymást

# Opcionális: állandó sorsolás a titkos SEED-del (Streamlit Secrets)
# Állíts be SEED és ADMIN_CODE értékeket a Streamlit Cloud "Secrets" részében.
SEED = st.secrets.get("SEED", None)           # pl. "2025"
ADMIN_CODE = st.secrets.get("ADMIN_CODE", "") # pl. "karacsony"

# --- App meta ---
st.set_page_config(page_title="Karácsonyi sorsolás 🎁", page_icon="🎄", layout="centered")
st.title("Karácsonyi Secret Santa 🎁")
st.caption("Saját neved kiválasztása után csak a **te** címzetted látszik. Párok és önmagad kizárva.")

# --- Sorsoló függvény (pár- és önkizárással) ---
def secret_santa(names, couples=None, seed=None, max_tries=10000):
    if seed not in (None, ""):
        random.seed(int(seed))

    if len(names) < 2:
        raise ValueError("Legalább 2 résztvevő kell.")

    # Tiltólisták felépítése (önmaga + párja)
    excl = {a: set([a]) for a in names}
    if couples:
        for a, b in couples:
            if a in excl and b in excl:
                excl[a].add(b)
                excl[b].add(a)

    allset = set(names)
    for a in names:
        if not (allset - excl[a]):
            raise ValueError(f"Nincs érvényes címzett: {a}")

    order = names[:]
    targets = names[:]
    for _ in range(max_tries):
        random.shuffle(order)
        random.shuffle(targets)
        used = set()
        asg = {}

        def back(i):
            if i == len(order):
                return True
            g = order[i]
            # jelöltek, akik még nem kaptak ajándékozót, és nem tiltottak
            cands = [t for t in targets if t not in used and t not in excl[g]]
            random.shuffle(cands)
            for t in cands:
                asg[g] = t
                used.add(t)
                # előretekintés: marad-e esély a többieknek?
                ok = True
                for g2 in order[i + 1:]:
                    if not any(x not in used and x not in excl[g2] for x in targets):
                        ok = False
                        break
                if ok and back(i + 1):
                    return True
                used.remove(t)
                del asg[g]
            return False

        if back(0):
            return asg

    raise RuntimeError("Nem találtam érvényes kiosztást. Próbáld más SEED-del.")

# --- Fix sorsolás előállítása a SEED alapján (ha megadva) ---
def get_mapping():
    try:
        return secret_santa(PARTICIPANTS, COUPLES, SEED)
    except Exception as e:
        st.error(f"Sorsolási hiba: {e}")
        st.stop()

MAPPING = get_mapping()

# --- URL paraméter: ?name=Valaki  -> előválasztjuk a nevet ---
qs = st.query_params
preselected_name = None
if "name" in qs and qs.get("name"):
    preselected_name = qs.get("name")
    try:
        # ha több "name" lenne, a query_params listát adhat vissza
        if isinstance(preselected_name, list):
            preselected_name = preselected_name[0]
    except Exception:
        pass

# --- Saját név kiválasztása + csak a saját címzett megjelenítése ---
st.subheader("Nézd meg, kit húztál")
select_default = PARTICIPANTS.index(preselected_name) if preselected_name in PARTICIPANTS else 0
me = st.selectbox("Válaszd ki a neved:", PARTICIPANTS, index=select_default, key="me")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Mutasd a címzettemet"):
        st.success(f"**{me}** húzta: **{MAPPING[me]}**")

with col2:
    # személyre szóló link generálása (?name=...)
    base_url = st.get_option("server.baseUrlPath") or ""
    # A Streamlit általában az aktuális oldal URL-jét használja, itt egyszerűen a query paramot adjuk hozzá.
    link = "?" + urllib.parse.urlencode({"name": me})
    st.link_button("Személyre szóló link", link, help="Ezt a linket küldheted tovább – megnyitáskor a te neved lesz kiválasztva.")

st.divider()

# --- Admin nézet: teljes lista + letöltés ---
with st.expander("Admin nézet (teljes lista és letöltés)"):
    code = st.text_input("Admin kód", type="password", help="Állíts be ADMIN_CODE értéket a Streamlit Secrets-ben.")
    if code and ADMIN_CODE and code == ADMIN_CODE:
        st.success("Admin mód engedélyezve.")
        st.table({
            "Adó": list(MAPPING.keys()),
            "Címzett": list(MAPPING.values())
        })
        # CSV letöltés
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["Adó", "Címzett"])
        for g, t in MAPPING.items():
            w.writerow([g, t])
        st.download_button("Letöltés CSV-ben", buf.getvalue().encode("utf-8"),
                           file_name="secret_santa.csv", mime="text/csv")
    else:
        st.info("Add meg az admin kódot a teljes lista megtekintéséhez.")
