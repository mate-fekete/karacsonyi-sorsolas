# app.py
import random
import csv
import io
import hmac
import hashlib
import urllib.parse
import streamlit as st

# --- Résztvevők és párok ---
PARTICIPANTS = ["Dóri", "Máté", "Bence", "Gréti", "Anya", "Csenge", "Geri"]
COUPLES = [("Dóri", "Máté"), ("Bence", "Gréti"), ("Csenge", "Geri")]  # ők nem húzhatják egymást

# --- Titkok a Streamlit Secrets-ből ---
SEED = st.secrets.get("SEED", None)               # pl. "2025"
ADMIN_CODE = st.secrets.get("ADMIN_CODE", "")     # pl. "karacsony"
LINK_SECRET = st.secrets.get("LINK_SECRET", "")   # pl. hosszú random string

# --- App meta ---
st.set_page_config(page_title="Karácsonyi sorsolás 🎁", page_icon="🎄", layout="centered")
st.title("Karácsonyi Secret Santa 🎁")
st.caption("Személyre szóló, lezárt linkekkel. Párok és önmagad kizárva.")

# --- HMAC segédek (lezárt linkekhez) ---
def make_token(name: str) -> str:
    if not LINK_SECRET:
        return ""
    key = LINK_SECRET.encode("utf-8")
    msg = name.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def valid_token(name: str, token: str) -> bool:
    if not LINK_SECRET or not token:
        return False
    expected = make_token(name)
    return hmac.compare_digest(expected, token)

# --- Sorsoló függvény ---
def secret_santa(names, couples=None, seed=None, max_tries=10000):
    if seed not in (None, ""):
        random.seed(int(seed))
    if len(names) < 2:
        raise ValueError("Legalább 2 résztvevő kell.")
    excl = {a: set([a]) for a in names}
    if couples:
        for a, b in couples:
            if a in excl and b in excl:
                excl[a].add(b); excl[b].add(a)
    allset = set(names)
    for a in names:
        if not (allset - excl[a]):
            raise ValueError(f"Nincs érvényes címzett: {a}")
    order = names[:]; targets = names[:]
    for _ in range(max_tries):
        random.shuffle(order); random.shuffle(targets)
        used=set(); asg={}
        def back(i):
            if i==len(order): return True
            g = order[i]
            cands = [t for t in targets if t not in used and t not in excl[g]]
            random.shuffle(cands)
            for t in cands:
                asg[g]=t; used.add(t)
                ok=True
                for g2 in order[i+1:]:
                    if not any(x not in used and x not in excl[g2] for x in targets):
                        ok=False; break
                if ok and back(i+1): return True
                used.remove(t); del asg[g]
            return False
        if back(0): return asg
    raise RuntimeError("Nem találtam érvényes kiosztást. Próbáld más SEED-del.")

def get_mapping():
    return secret_santa(PARTICIPANTS, COUPLES, SEED)

try:
    MAPPING = get_mapping()
except Exception as e:
    st.error(f"Sorsolási hiba: {e}")
    st.stop()

# --- Query paramok ---
qs = st.query_params
qp_name = None
qp_token = None
if "name" in qs and qs.get("name"):
    qp_name = qs.get("name")
    if isinstance(qp_name, list):
        qp_name = qp_name[0]
if "k" in qs and qs.get("k"):
    qp_token = qs.get("k")
    if isinstance(qp_token, list):
        qp_token = qp_token[0]

# --- Lezárt mód eldöntése ---
locked_mode = False
locked_error = None
if qp_name:
    if qp_name not in PARTICIPANTS:
        locked_mode = True
        locked_error = "Érvénytelen név a linkben."
    else:
        if valid_token(qp_name, qp_token):
            locked_mode = True
        else:
            locked_mode = True
            locked_error = "Érvénytelen vagy hiányzó token a linkben."

# --- UI ---

if locked_mode:
    st.subheader("Személyre szóló nézet (lezárt link)")
    if locked_error:
        st.error(locked_error)
        st.stop()

    who = qp_name

    # 🔒 NE mutassuk azonnal — csak gombnyomásra
    st.info("Ez egy személyre szóló, lezárt link. Az eredmény csak gombnyomásra látható.")
    reveal_key = f"revealed::{who}"
    if reveal_key not in st.session_state:
        st.session_state[reveal_key] = False

    if not st.session_state[reveal_key]:
        if st.button("Húzás megtekintése"):
            st.session_state[reveal_key] = True
            st.rerun()
        st.stop()

    # Ha megnyomta a gombot, ekkor mutatjuk meg:
    st.success(f"**{who}** húzta: **{MAPPING[who]}**")
    st.caption("Ha nem a te linked nyílt meg, zárd be az oldalt, ne nézd meg másét. 😉")

else:
    st.subheader("Névválasztós nézet (általános)")
    me = st.selectbox("Válaszd ki a neved:", PARTICIPANTS, index=0, key="me")
    col1, col2 = st.columns([1,1])

    with col1:
        if st.button("Mutasd a címzettemet"):
            st.success(f"**{me}** húzta: **{MAPPING[me]}**")

    with col2:
        if not LINK_SECRET:
            st.warning("LINK_SECRET hiányzik a Secrets-ből, így a lezárt linkek nem elérhetők.")
        else:
            token = make_token(me)
            qp = urllib.parse.urlencode({"name": me, "k": token})
            link_suffix = "?" + qp
            st.link_button("Személyre szóló lezárt link", link_suffix,
                           help="Ezt a linket küldheted tovább – csak gombnyomásra jelenik meg az eredmény.")

st.divider()

# --- Admin nézet ---
with st.expander("Admin nézet (teljes lista és személyre szóló linkek)"):
    code = st.text_input("Admin kód", type="password")
    if code and ADMIN_CODE and code == ADMIN_CODE:
        st.success("Admin mód engedélyezve.")

        st.markdown("**Teljes párosítás**")
        st.table({"Adó": list(MAPPING.keys()), "Címzett": list(MAPPING.values())})

        st.markdown("**Letöltés CSV-ben**")
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["Adó", "Címzett"])
        for g, t in MAPPING.items():
            w.writerow([g, t])
        st.download_button("Letöltés CSV-ben", buf.getvalue().encode("utf-8"),
                           file_name="secret_santa.csv", mime="text/csv")

        st.markdown("**Személyre szóló lezárt linkek (query param rész)**")
        if not LINK_SECRET:
            st.warning("LINK_SECRET hiányzik, így nem lehet biztonságos linket generálni.")
        else:
            rows = {"Név": [], "Query param": []}
            for name in PARTICIPANTS:
                token = make_token(name)
                qp = urllib.parse.urlencode({"name": name, "k": token})
                rows["Név"].append(name)
                rows["Query param"].append("?" + qp)
            st.table(rows)
            st.info(
                "A „Query param” részt illeszd az app fő URL-je mögé.\n"
                "Példa: https://SAJAT-APPOD.streamlit.app" + rows["Query param"][0]
            )
    else:
        st.info("Add meg az admin kódot a teljes lista és a lezárt linkek megjelenítéséhez.")
