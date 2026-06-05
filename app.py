"""
Interface Streamlit — À CRÉER PAR VOUS pour le jury.

Le jury lancera :  streamlit run app.py

Règles :
  - Ne modifiez pas l'appel à detect_fraud / load_transactions (contrat technique).
  - Personnalisez render_interface() : clarté, intuitivité, compréhension pour un public non technique.
  - L'interface n'est PAS notée par la CI ; elle sert au jury pour repêcher et comparer les candidats.
"""

from pathlib import Path

import streamlit as st

from fraud_detection import detect_fraud, load_transactions

SAMPLE_CSV = Path(__file__).parent / "data" / "sample_transactions.csv"


# Centroïdes géographiques des pays (latitude, longitude)
_COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "FR": (46.23, 2.21),
    "DE": (51.17, 10.45),
    "GB": (55.38, -3.44),
    "ES": (40.46, -3.75),
    "IT": (41.87, 12.57),
    "US": (37.09, -95.71),
    "CA": (56.13, -106.35),
    "MX": (23.63, -102.55),
    "BR": (-14.24, -51.93),
    "JP": (36.20, 138.25),
    "CN": (35.86, 104.20),
    "IN": (20.59, 78.96),
    "AU": (-25.27, 133.78),
    "ZA": (-30.56, 22.94),
    "SN": (14.50, -14.45),
    "CI": (7.54, -5.55),
    "NG": (9.08, 8.68),
    "MA": (31.79, -7.09),
    "TG": (8.62, 0.82),
    "CM": (3.85, 11.50),
}


def _kpi_card(label: str, value: str, subtitle: str, bg: str, text: str) -> str:
    return (
        f'<div style="background:{bg}; border-radius:12px; padding:1rem 1.2rem; text-align:center;">'
        f'<div style="color:{text}; font-size:0.8rem; font-weight:600; text-transform:uppercase; '
        f'letter-spacing:0.05em; margin-bottom:0.3rem;">{label}</div>'
        f'<div style="color:{text}; font-size:2rem; font-weight:800; line-height:1;">{value}</div>'
        f'<div style="color:{text}; opacity:0.75; font-size:0.78rem; margin-top:0.3rem;">{subtitle}</div>'
        f'</div>'
    )


def _progress_bar(val: float, color: str) -> str:
    pct = int(val * 100)
    return (
        f'<div style="background:#2a2a2a; border-radius:4px; height:8px; width:100%; margin:2px 0 4px;">'
        f'<div style="background:{color}; width:{pct}%; height:100%; border-radius:4px;"></div>'
        f'</div>'
        f'<span style="font-size:0.75rem; color:{color}; font-weight:600;">{val:.2f}</span>'
    )


def render_interface(transactions: list[dict], results: list[dict]) -> None:
    """Interface de présentation des résultats d'analyse de fraude pour le jury."""
    import pandas as pd

    tx_by_id = {tx["transaction_id"]: tx for tx in transactions}
    rows = []
    for r in results:
        tid = r["transaction_id"]
        tx = tx_by_id.get(tid, {})
        rows.append({
            "ID": tid,
            "Utilisateur": tx.get("user_id", "-"),
            "Montant": tx.get("amount"),
            "Devise": tx.get("currency", "-"),
            "Commerçant": tx.get("merchant", "-"),
            "Pays": tx.get("country", "-"),
            "Date": tx.get("timestamp", "-"),
            "Score de risque": r["fraud_score"],
            "Score règles": r.get("_rule_score", 0.0),
            "Score IA": r.get("_ml_score", 0.0),
            "Score composite": r.get("_composite_score", 0.0),
            "Verdict": "Alerte" if r["is_suspicious"] else "Normal",
            "Explication": r["reason"],
        })
    df = pd.DataFrame(rows)

    total = len(results)
    nb_alerts = sum(1 for r in results if r["is_suspicious"])
    pct = nb_alerts / total * 100 if total else 0
    avg_score = sum(r["fraud_score"] for r in results) / total if total else 0

    # --- Bandeau contextuel ---
    if nb_alerts > 0:
        st.markdown(
            f'<div style="background:linear-gradient(90deg,#922b21,#c0392b); color:white; '
            f'border-radius:10px; padding:0.8rem 1.4rem; margin:0.8rem 0; font-size:1rem;">'
            f'<strong>Attention :</strong> {nb_alerts} transaction(s) suspecte(s) détectée(s) '
            f'sur {total} — vérification recommandée.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="background:linear-gradient(90deg,#1a6635,#27ae60); color:white; '
            f'border-radius:10px; padding:0.8rem 1.4rem; margin:0.8rem 0; font-size:1rem;">'
            f'Aucune anomalie détectée — toutes les transactions semblent conformes.</div>',
            unsafe_allow_html=True,
        )

    # --- KPI cards colorées ---
    avg_color = "#c0392b" if avg_score >= 0.5 else ("#e67e22" if avg_score >= 0.3 else "#27ae60")
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(_kpi_card("Transactions", str(total), "analysées", "#1e2a3a", "white"), unsafe_allow_html=True)
    col2.markdown(_kpi_card("Alertes", str(nb_alerts), f"{pct:.0f}% du total", "#4a1010" if nb_alerts else "#1a3a20", "#e74c3c" if nb_alerts else "#2ecc71"), unsafe_allow_html=True)
    col3.markdown(_kpi_card("Sûres", str(total - nb_alerts), "transactions normales", "#1a3a20", "#2ecc71"), unsafe_allow_html=True)
    col4.markdown(_kpi_card("Score moyen", f"{avg_score:.2f}", "sur 1.00", "#1e2a3a", avg_color), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # --- Carte géographique ---
    st.subheader("Carte géographique des transactions")
    map_rows = []
    for r in results:
        tid = r["transaction_id"]
        tx = tx_by_id.get(tid, {})
        country = tx.get("country")
        coords = _COUNTRY_COORDS.get(country or "")
        if coords:
            is_alert = r["is_suspicious"]
            map_rows.append({
                "lat": coords[0],
                "lon": coords[1],
                "color": [192, 57, 43, 200] if is_alert else [39, 174, 96, 160],
                "radius": int(200_000 * max(r["fraud_score"], 0.1)),
                "tooltip": (
                    f"ID: {tid} | Utilisateur: {tx.get('user_id', '-')} | "
                    f"Montant: {tx.get('amount', '-')} {tx.get('currency', '')} | "
                    f"Score: {r['fraud_score']:.2f} | {r['reason']}"
                ),
            })

    if map_rows:
        try:
            import pydeck as pdk
            map_df = pd.DataFrame(map_rows)
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=map_df,
                get_position="[lon, lat]",
                get_fill_color="color",
                get_radius="radius",
                pickable=True,
            )
            view = pdk.ViewState(latitude=20, longitude=10, zoom=1.2, pitch=0)
            st.pydeck_chart(
                pdk.Deck(
                    layers=[layer],
                    initial_view_state=view,
                    tooltip={"text": "{tooltip}"},
                    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                )
            )
            st.caption("Rouge = alerte · Vert = normal · Taille proportionnelle au score de risque")
        except Exception:
            st.info("Carte indisponible (pydeck non installé). Installez-le avec : pip install pydeck")
    else:
        st.info("Aucun pays reconnu dans les données — carte non disponible.")

    # --- Filtre et tableau principal ---
    st.markdown("---")
    st.subheader("Tableau des transactions")
    filtre = st.radio(
        "Afficher :",
        ["Toutes", "Alertes uniquement", "Normales uniquement"],
        horizontal=True,
    )
    if filtre == "Alertes uniquement":
        df_view = df[df["Verdict"] == "Alerte"]
    elif filtre == "Normales uniquement":
        df_view = df[df["Verdict"] == "Normal"]
    else:
        df_view = df

    def _color_verdict(val):
        if val == "Alerte":
            return "background-color: #ffeaea; color: #c0392b; font-weight: bold"
        return "background-color: #eafaf1; color: #1e8449"

    def _color_score(val):
        if val >= 0.8:
            return "color: #c0392b; font-weight: bold"
        if val >= 0.5:
            return "color: #e67e22; font-weight: bold"
        return "color: #27ae60"

    cols_display = ["ID", "Utilisateur", "Montant", "Devise", "Commerçant", "Pays",
                    "Date", "Score de risque", "Verdict", "Explication"]
    styled = (
        df_view[cols_display].style
        .map(_color_verdict, subset=["Verdict"])
        .map(_color_score, subset=["Score de risque"])
        .format({"Score de risque": "{:.2f}", "Montant": lambda v: f"{v:,.2f}" if v is not None else "—"})
    )
    st.dataframe(styled, width="stretch", hide_index=True)

    # --- Décomposition Score IA vs Règles ---
    st.markdown("---")
    st.subheader("Décomposition du score : Règles vs IA vs Signaux composites")

    for r in results:
        tid = r["transaction_id"]
        tx = tx_by_id.get(tid, {})
        is_alert = r["is_suspicious"]
        border = "#c0392b" if is_alert else "#27ae60"
        icon = "🔴" if is_alert else "🟢"
        rule_s = r.get("_rule_score", 0.0)
        comp_s = r.get("_composite_score", 0.0)
        ml_s = r.get("_ml_score", 0.0)
        final_s = r["fraud_score"]

        rule_color = "#c0392b" if rule_s >= 0.5 else ("#e67e22" if rule_s > 0 else "#555")
        comp_color = "#e67e22" if comp_s >= 0.3 else ("#f39c12" if comp_s > 0 else "#555")
        ml_color = "#3498db"
        final_color = "#c0392b" if final_s >= 0.5 else "#27ae60"

        st.markdown(
            f'<div style="border-left:4px solid {border}; padding:0.6rem 1rem; '
            f'margin-bottom:0.5rem; background:#1a1a1a; border-radius:0 8px 8px 0;">'
            f'<div style="font-weight:700; margin-bottom:0.4rem;">'
            f'{icon} {tid} <span style="color:#888; font-weight:400; font-size:0.85rem;">({tx.get("user_id","-")})</span></div>'
            f'<div style="display:flex; gap:1.5rem; align-items:flex-start; flex-wrap:wrap;">'
            f'<div style="min-width:120px;"><div style="color:#aaa; font-size:0.72rem; margin-bottom:2px;">RÈGLES</div>'
            f'{_progress_bar(rule_s, rule_color)}</div>'
            f'<div style="min-width:120px;"><div style="color:#aaa; font-size:0.72rem; margin-bottom:2px;">COMPOSITE</div>'
            f'{_progress_bar(comp_s, comp_color)}</div>'
            f'<div style="min-width:120px;"><div style="color:#aaa; font-size:0.72rem; margin-bottom:2px;">IA</div>'
            f'{_progress_bar(ml_s, ml_color)}</div>'
            f'<div style="min-width:80px;"><div style="color:#aaa; font-size:0.72rem; margin-bottom:2px;">SCORE FINAL</div>'
            f'<div style="color:{final_color}; font-size:1.3rem; font-weight:800; line-height:1;">{final_s:.2f}</div></div>'
            f'</div>'
            f'<div style="color:#aaa; font-size:0.78rem; margin-top:0.3rem; font-style:italic;">{r["reason"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- Détail par client ---
    st.markdown("---")
    st.subheader("Analyse par client")
    users = sorted(df["Utilisateur"].unique())
    for uid in users:
        user_df = df[df["Utilisateur"] == uid]
        user_alerts = user_df[user_df["Verdict"] == "Alerte"]
        nb_u = len(user_df)
        nb_a = len(user_alerts)
        badge = f' <span style="background:#c0392b;color:white;border-radius:10px;padding:1px 8px;font-size:0.75rem;">{nb_a} alerte(s)</span>' if nb_a else ""
        label = f"{uid} — {nb_u} transaction(s)"
        if nb_a:
            label += f" · {nb_a} alerte(s)"
        with st.expander(label, expanded=nb_a > 0):
            cards_html = '<div style="display:flex; flex-wrap:wrap; gap:0.6rem; padding:0.4rem 0;">'
            for _, row in user_df.iterrows():
                is_alert = row["Verdict"] == "Alerte"
                bg = "#3a1010" if is_alert else "#0f2a18"
                border_c = "#c0392b" if is_alert else "#27ae60"
                score_pct = int(row["Score de risque"] * 100)
                montant = f"{row['Montant']:,.2f} {row['Devise']}" if row["Montant"] is not None else "—"
                verdict_label = "ALERTE" if is_alert else "NORMAL"
                verdict_color = "#e74c3c" if is_alert else "#2ecc71"
                cards_html += (
                    f'<div style="background:{bg}; border:1px solid {border_c}; border-radius:10px; '
                    f'padding:0.7rem 1rem; min-width:220px; flex:1;">'
                    f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                    f'<span style="font-weight:700; font-size:0.9rem;">{row["ID"]}</span>'
                    f'<span style="color:{verdict_color}; font-size:0.72rem; font-weight:700;">{verdict_label}</span>'
                    f'</div>'
                    f'<div style="font-size:1.2rem; font-weight:800; margin:0.2rem 0; color:white;">{montant}</div>'
                    f'<div style="color:#aaa; font-size:0.75rem;">{row["Pays"]} · {row["Commerçant"]}</div>'
                    f'<div style="background:#333; border-radius:4px; height:6px; margin:0.4rem 0;">'
                    f'<div style="background:{border_c}; width:{score_pct}%; height:100%; border-radius:4px;"></div>'
                    f'</div>'
                    f'<div style="color:#bbb; font-size:0.72rem; font-style:italic;">{row["Explication"]}</div>'
                    f'</div>'
                )
            cards_html += '</div>'
            st.markdown(cards_html, unsafe_allow_html=True)

    # --- Explication du système ---
    st.markdown("---")
    with st.expander("Comment fonctionne la détection ?"):
        st.markdown(
            """
**Architecture en deux couches :**

**Couche 1 — Règles déterministes (priorité absolue)**

| Signal | Score |
|--------|-------|
| Montant nul ou négatif | 0.90 |
| Montant > 10× la moyenne du client | 0.90 |
| Voyage impossible (2 pays en < 6h) | 0.88 |
| Champ pays manquant | 0.85 |
| Fréquence > 5 transactions / heure | 0.75 |

**Couche 2 — Signaux faibles cumulés + IA (Isolation Forest)**

Chaque signal faible s'additionne. Seul il ne suffit pas, mais plusieurs combinés déclenchent une alerte :

| Signal faible | Contribution |
|---|---|
| Montant entre 3× et 10× la moyenne | +0.20 à +0.25 |
| Transaction nocturne (01h–05h) | +0.15 |
| Nouveau pays pour ce client | +0.15 |
| Carte physique absente | +0.10 |
| Intervalle < 2 min depuis la dernière | +0.20 |
| Score Isolation Forest (IA) | jusqu'à +0.40 |

Une transaction est **signalée comme alerte** si le score final dépasse **0.50**.
            """
        )

    # --- Graphique de distribution ---
    st.markdown("---")
    st.subheader("Distribution des scores de risque")
    score_df = pd.DataFrame({
        "Score": [r["fraud_score"] for r in results],
        "Statut": ["Alerte" if r["is_suspicious"] else "Normal" for r in results],
    })
    st.bar_chart(score_df.set_index("Score").groupby(level=0).count())


def main() -> None:
    st.set_page_config(
        page_title="Détection de fraude — Hackathon INTELO2026",
        page_icon="🛡️",
        layout="wide",
    )

    st.markdown(
        """
        <div style="background: linear-gradient(90deg, #c0392b, #e74c3c);
                    padding: 1.2rem 2rem; border-radius: 10px; margin-bottom: 1rem;">
            <h1 style="color: white; margin: 0; font-size: 2rem;">Détection de fraude financière</h1>
            <p style="color: rgba(255,255,255,0.85); margin: 0.3rem 0 0 0; font-size: 0.9rem;">
                Analyse intelligente des transactions · Hackathon INTELO2026
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            '<div style="background:#1e2a3a; border-radius:10px; padding:0.8rem 1rem; margin-bottom:1rem;">'
            '<div style="color:white; font-weight:700; font-size:1rem;">Données d\'analyse</div>'
            '<div style="color:#aaa; font-size:0.75rem;">Chargez un fichier CSV de transactions</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        use_sample = st.toggle("Utiliser le fichier d'exemple", value=True)
        transactions: list[dict] = []

        if use_sample:
            transactions = load_transactions(str(SAMPLE_CSV))
            st.success(f"{len(transactions)} transactions chargées")
        else:
            uploaded = st.file_uploader("Importer un CSV", type=["csv"])
            if uploaded:
                tmp = Path(".streamlit_upload.csv")
                tmp.write_bytes(uploaded.getvalue())
                transactions = load_transactions(str(tmp))
                tmp.unlink(missing_ok=True)
                st.success(f"{len(transactions)} transactions importées")

        st.divider()
        st.caption("Colonnes attendues : transaction_id, user_id, amount, currency, merchant, country, card_present, timestamp.")

    if not transactions:
        st.info("Chargez des transactions (barre latérale) puis lancez l'analyse.")
        st.session_state.pop("results", None)
        st.session_state.pop("transactions", None)
        return

    if st.button("Analyser", type="primary"):
        try:
            results = detect_fraud(transactions)
            st.session_state["results"] = results
            st.session_state["transactions"] = transactions
        except NotImplementedError:
            st.error("Implémentez d'abord `detect_fraud` dans `fraud_detection.py`.")
            return
        except Exception as exc:
            st.error(f"Erreur : {exc}")
            return

    if "results" in st.session_state and "transactions" in st.session_state:
        render_interface(st.session_state["transactions"], st.session_state["results"])


if __name__ == "__main__":
    main()
