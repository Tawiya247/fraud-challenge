"""
Défi — Détection de fraude financière.

Vous devez implémenter la fonction `detect_fraud`.
La fonction `load_transactions` vous est FOURNIE (ne la modifiez pas).
"""

import csv


def load_transactions(path):
    """Lit un fichier CSV de transactions et renvoie une liste de dicts."""
    transactions = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(_clean_row(row))
    return transactions


def _clean_row(row):
    def get(key):
        v = row.get(key)
        return v.strip() if isinstance(v, str) and v.strip() != "" else None

    amount_raw = get("amount")
    try:
        amount = float(amount_raw) if amount_raw is not None else None
    except ValueError:
        amount = None

    card_raw = get("card_present")
    if card_raw is None:
        card_present = None
    else:
        card_present = card_raw.lower() in ("true", "1", "yes", "oui")

    return {
        "transaction_id": get("transaction_id"),
        "timestamp": get("timestamp"),
        "user_id": get("user_id"),
        "amount": amount,
        "currency": get("currency"),
        "merchant": get("merchant"),
        "country": get("country"),
        "card_present": card_present,
    }


def detect_fraud(transactions):
    """Analyse une liste de transactions et renvoie un verdict pour chacune.

    Retour : list[dict] avec transaction_id, fraud_score (0-1),
    is_suspicious (bool), reason (str) — un résultat par transaction, même ordre.

    Architecture en deux couches :
    1. Règles déterministes (priorité absolue) pour les anomalies évidentes.
    2. Score composite (cumul de signaux faibles) + Isolation Forest (IA) pour
       les cas subtils que les règles seules ne captent pas.
    """
    from datetime import datetime

    # ------------------------------------------------------------------ #
    #  Pré-calcul : stats par utilisateur                                  #
    # ------------------------------------------------------------------ #
    user_txns: dict[str, list] = {}
    for tx in transactions:
        uid = tx.get("user_id")
        if uid:
            user_txns.setdefault(uid, []).append(tx)

    user_avg: dict[str, float] = {}
    user_countries: dict[str, set] = {}
    for uid, txns in user_txns.items():
        amounts = [t["amount"] for t in txns if t.get("amount") is not None and t["amount"] > 0]
        if amounts:
            user_avg[uid] = sum(amounts) / len(amounts)
        countries = {t["country"] for t in txns if t.get("country")}
        user_countries[uid] = countries

    def _parse_ts(ts_str):
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def _impossible_travel(tx, all_user_txns):
        """Détecte un voyage physiquement impossible (deux pays en < 6h)."""
        country = tx.get("country")
        ts = _parse_ts(tx.get("timestamp"))
        tid = tx.get("transaction_id")
        if not country or not ts:
            return False
        for other in all_user_txns:
            if other.get("transaction_id") == tid:
                continue
            other_country = other.get("country")
            other_ts = _parse_ts(other.get("timestamp"))
            if not other_country or not other_ts or other_country == country:
                continue
            if abs((ts - other_ts).total_seconds()) / 3600 < 6:
                return True
        return False

    def _high_frequency(tx, all_user_txns):
        """Détecte > 5 transactions du même client en 1 heure."""
        ts = _parse_ts(tx.get("timestamp"))
        tid = tx.get("transaction_id")
        if not ts:
            return False
        count = sum(
            1 for other in all_user_txns
            if other.get("transaction_id") != tid
            and _parse_ts(other.get("timestamp")) is not None
            and abs((ts - _parse_ts(other.get("timestamp"))).total_seconds()) <= 3600
        )
        return count >= 5

    def _time_since_last(tx, all_user_txns):
        """Renvoie le délai en minutes depuis la transaction précédente, ou None."""
        ts = _parse_ts(tx.get("timestamp"))
        tid = tx.get("transaction_id")
        if not ts:
            return None
        others = [
            _parse_ts(o.get("timestamp"))
            for o in all_user_txns
            if o.get("transaction_id") != tid and _parse_ts(o.get("timestamp")) is not None
        ]
        if not others:
            return None
        diffs = [abs((ts - o).total_seconds()) / 60 for o in others]
        return min(diffs)

    # ------------------------------------------------------------------ #
    #  Couche IA : Isolation Forest                                        #
    # ------------------------------------------------------------------ #
    ml_scores: dict[str, float] = {}
    if len(transactions) >= 5:
        try:
            import numpy as np
            from sklearn.ensemble import IsolationForest

            feature_rows = []
            for tx in transactions:
                uid = tx.get("user_id")
                amount = tx.get("amount") or 0
                avg = user_avg.get(uid, 1) or 1
                ts = _parse_ts(tx.get("timestamp"))
                hour = ts.hour if ts else 12
                card = 0.0 if tx.get("card_present") is False else 1.0
                known_country = 1.0 if tx.get("country") in user_countries.get(uid or "", set()) else 0.0
                delay = _time_since_last(tx, user_txns.get(uid or "", [])) or 9999
                feature_rows.append([
                    min(amount / avg, 100),
                    card,
                    hour,
                    known_country,
                    min(delay, 9999),
                ])

            X = np.array(feature_rows, dtype=float)
            clf = IsolationForest(contamination=0.1, random_state=42)
            clf.fit(X)
            raw = clf.score_samples(X)
            lo, hi = raw.min(), raw.max()
            for i, tx in enumerate(transactions):
                if hi == lo:
                    ml_scores[tx.get("transaction_id")] = 0.0
                else:
                    normalized = 1.0 - (raw[i] - lo) / (hi - lo)
                    ml_scores[tx.get("transaction_id")] = float(min(normalized * 0.4, 0.4))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Analyse transaction par transaction                                 #
    # ------------------------------------------------------------------ #
    results = []
    for tx in transactions:
        tid = tx.get("transaction_id")
        amount = tx.get("amount")
        user_id = tx.get("user_id")
        country = tx.get("country")
        ts = _parse_ts(tx.get("timestamp"))
        utxns = user_txns.get(user_id or "", [])

        rule_score = 0.0
        rule_reason = ""

        # — Règles évidentes (priorité absolue, score figé) —
        if amount is None:
            rule_score = 0.85
            rule_reason = "Montant manquant"
        elif amount <= 0:
            rule_score = 0.9
            rule_reason = "Montant nul ou négatif"
        elif country is None:
            rule_score = 0.85
            rule_reason = "Champs obligatoires manquants: country"
        elif _impossible_travel(tx, utxns):
            rule_score = 0.88
            rule_reason = "Deux pays différents en trop peu de temps"
        elif user_id and amount > 0:
            avg = user_avg.get(user_id)
            if avg and avg > 0:
                ratio = amount / avg
                if ratio > 10:
                    rule_score = 0.9
                    rule_reason = "Montant très supérieur à l'habitude du client"
        elif _high_frequency(tx, utxns):
            rule_score = 0.75
            rule_reason = "Fréquence de transactions suspecte"

        # — Score composite (cumul de signaux faibles) —
        composite = 0.0
        composite_signals = []

        if rule_score == 0.0 and amount is not None and amount > 0:
            avg = user_avg.get(user_id or "")
            if avg and avg > 0:
                ratio = amount / avg
                if 5 < ratio <= 10:
                    composite += 0.25
                    composite_signals.append("montant élevé")
                elif 3 < ratio <= 5:
                    composite += 0.20
                    composite_signals.append("montant modérément élevé")

            if ts and ts.hour in range(1, 6):
                composite += 0.15
                composite_signals.append("heure nocturne")

            if tx.get("card_present") is False:
                composite += 0.10
                composite_signals.append("carte absente")

            if user_id and country and country not in user_countries.get(user_id, set()):
                prior_countries = user_countries.get(user_id, set()) - {country}
                if prior_countries:
                    composite += 0.15
                    composite_signals.append("nouveau pays")

            delay = _time_since_last(tx, utxns)
            if delay is not None and delay < 2:
                composite += 0.20
                composite_signals.append("intervalle très court")

        # — Fusion des scores —
        ml = ml_scores.get(tid, 0.0)

        if rule_score > 0:
            final_score = rule_score
            reason = rule_reason
        elif composite > 0 or ml > 0:
            final_score = min(1.0, composite + ml)
            if composite_signals:
                reason = "Combinaison de signaux suspects : " + ", ".join(composite_signals)
            elif final_score >= 0.5:
                reason = "Anomalie détectée par analyse statistique"
            else:
                reason = "Transaction conforme au profil du client"
        else:
            final_score = 0.0
            reason = "Transaction conforme au profil du client"

        results.append({
            "transaction_id": tid,
            "fraud_score": round(float(final_score), 4),
            "is_suspicious": final_score >= 0.5,
            "reason": reason,
            "_rule_score": round(float(rule_score), 4),
            "_ml_score": round(float(ml), 4),
            "_composite_score": round(float(composite), 4),
        })

    return results
