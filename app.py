"""
Customs@SG – Traveller Portal
Personal Information Page Prototype

Two variants (radio — not tabs, so widget state survives on Streamlit Cloud):
  1. Baseline Form
  2. Improved Form with MyInfo Autofill

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import re
import time
import streamlit as st
from datetime import date, timedelta

# ──────────────────────────────────────────────
# Constants / static data
# ──────────────────────────────────────────────

DECLARATION_TYPES = ["Traveller", "Crew Member", "Commercial"]
DOC_TYPES = ["NRIC", "FIN", "Passport"]
PERIOD_AWAY_OPTIONS = [
    "Less than 48 hours",
    "48 hours or more",
]
NATIONALITIES = [
    "Singapore (SGP)",
    "Malaysia (MYS)",
    "Indonesia (IDN)",
    "China (CHN)",
    "India (IND)",
    "United States (USA)",
    "United Kingdom (GBR)",
]

MOCK_MYINFO = {
    "name": "John Test",
    "email": "jontaygc@hotmail.com",
    "phone": "91257076",
}

# ──────────────────────────────────────────────
# Validation helpers
# ──────────────────────────────────────────────

def validate_nric(value: str) -> bool:
    """S/T + 7 digits + letter"""
    return bool(re.fullmatch(r"[STst]\d{7}[A-Za-z]", value))

def validate_fin(value: str) -> bool:
    """F/G/M + 7 digits + letter"""
    return bool(re.fullmatch(r"[FGMfgm]\d{7}[A-Za-z]", value))

def validate_passport(value: str) -> bool:
    """Up to 9 alphanumeric characters, at least 1"""
    return bool(re.fullmatch(r"[A-Za-z0-9]{1,9}", value))

def validate_passport_expiry(d: date) -> bool:
    today = date.today()
    max_date = today + timedelta(days=365 * 10 + 1)
    return today <= d <= max_date

def validate_email(value: str) -> bool:
    if len(value) > 320:
        return False
    pattern = r"^[^@]{1,64}@[^@]{1,255}$"
    if not re.match(pattern, value):
        return False
    # Basic structure check
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))

def validate_phone(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6,12}", value))

def validate_name(value: str) -> bool:
    return 1 <= len(value) <= 66

def validate_importer_name(value: str) -> bool:
    return 1 <= len(value) <= 50 and bool(re.fullmatch(r"[A-Za-z0-9 ]*", value))

def validate_uen(value: str) -> bool:
    return len(value) <= 10 and bool(re.fullmatch(r"[A-Za-z0-9]*", value))

# ──────────────────────────────────────────────
# Session-state initialisation
# ──────────────────────────────────────────────

def _init_state(prefix: str):
    """Initialise all form keys under `prefix` if not already present."""
    # Baseline tab: no declaration/document chosen until the user clicks a pill (no default highlight).
    decl0 = None if prefix == "base" else "Traveller"
    doc0 = None if prefix == "base" else "NRIC"
    defaults = {
        f"{prefix}_decl_type": decl0,
        f"{prefix}_doc_type": doc0,
        f"{prefix}_pass_holder": None,          # None = not selected yet
        f"{prefix}_period_away": None,
        f"{prefix}_nric": "",
        f"{prefix}_fin": "",
        f"{prefix}_passport_no": "",
        f"{prefix}_passport_expiry": None,
        f"{prefix}_nationality": "",
        f"{prefix}_name": "",
        f"{prefix}_email": "",
        f"{prefix}_phone": "",
        f"{prefix}_importer_name": "",
        f"{prefix}_uen": "",
        # UX timing (Baseline tab only)
        f"{prefix}_started_at": None,          # time.time() at first click/input
        f"{prefix}_time_to_next_sec": None,   # seconds from first interaction to "Next"
        f"{prefix}_next_clicked": False,
        # MyInfo autofill flags (only used in improved tab)
        f"{prefix}_sp_name_autofilled": False,
        f"{prefix}_sp_email_autofilled": False,
        f"{prefix}_sp_phone_autofilled": False,
        f"{prefix}_singpass_used": False,
        # Bumped on MyInfo so text widgets get fresh keys (Cloud-safe autofill via value=).
        f"{prefix}_myinfo_stamp": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ──────────────────────────────────────────────
# Derived state helpers
# ──────────────────────────────────────────────

def get_effective_pass_holder(prefix: str) -> str | None:
    """Return auto-resolved or user-selected pass-holder value."""
    doc = st.session_state[f"{prefix}_doc_type"]
    if doc is None:
        return None
    if doc == "FIN":
        return "Yes"
    # NRIC/Passport – return whatever user picked (may be None)
    return st.session_state[f"{prefix}_pass_holder"]

# ──────────────────────────────────────────────
# Field visibility logic
# ──────────────────────────────────────────────

def visible_fields(prefix: str, with_singpass: bool) -> dict:
    """Return a dict of field_name -> bool (visible/required?)"""
    decl = st.session_state[f"{prefix}_decl_type"]
    doc  = st.session_state[f"{prefix}_doc_type"]
    is_traveller   = decl == "Traveller"
    is_crew        = decl == "Crew Member"
    is_commercial  = decl == "Commercial"

    # Baseline form asks the "Are you a Singapore pass-holder?" question only for NRIC/FIN.
    # Improved MyInfo form hides that question entirely.
    show_pass_holder = (not with_singpass) and is_traveller and doc in ("NRIC", "FIN")
    show_period = (
        (is_traveller) and doc in ("NRIC", "Passport")
    )

    return {
        "decl_type":       (not with_singpass),
        "doc_type":        (not with_singpass),
        "pass_holder":     show_pass_holder,
        "period_away":     show_period,
        "nric":            doc == "NRIC",
        "fin":             doc == "FIN",
        "passport_no":     doc == "Passport",
        "passport_expiry": doc == "Passport",
        "nationality":     doc == "Passport",
        "name":            True,
        "email":           True,
        "phone":           True,
        "importer_name":   is_commercial,
        "uen":             is_commercial,
    }

# ──────────────────────────────────────────────
# Per-field validation (returns error string or "")
# ──────────────────────────────────────────────

def field_errors(prefix: str, with_singpass: bool) -> dict:
    s = st.session_state
    errors: dict[str, str] = {}
    if not with_singpass:
        if s[f"{prefix}_decl_type"] is None:
            errors["decl_type"] = "Please select a type of declaration"
        if s[f"{prefix}_doc_type"] is None:
            errors["doc_type"] = "Please select a travel document type"
        if s[f"{prefix}_decl_type"] is None or s[f"{prefix}_doc_type"] is None:
            return errors

    vis = visible_fields(prefix, with_singpass)

    if vis["nric"] and not validate_nric(s[f"{prefix}_nric"]):
        errors["nric"] = "Please enter a valid NRIC (e.g. S1234567D)"

    if vis["fin"] and not validate_fin(s[f"{prefix}_fin"]):
        errors["fin"] = "Please enter a valid FIN (e.g. F9989472P)"

    if vis["passport_no"] and not validate_passport(s[f"{prefix}_passport_no"]):
        errors["passport_no"] = "Please enter a valid Passport No. (up to 9 alphanumeric characters)"

    if vis["passport_expiry"]:
        exp = s[f"{prefix}_passport_expiry"]
        if exp is None or not validate_passport_expiry(exp):
            errors["passport_expiry"] = "Please enter a valid expiry date"

    if vis["nationality"] and not s[f"{prefix}_nationality"]:
        errors["nationality"] = "Please select a nationality"

    if vis["pass_holder"] and s[f"{prefix}_pass_holder"] is None:
        errors["pass_holder"] = "Please indicate whether you are a Singapore pass-holder"

    if vis["period_away"] and not s[f"{prefix}_period_away"]:
        errors["period_away"] = "Please select a period away from Singapore"

    if not validate_name(s[f"{prefix}_name"]):
        errors["name"] = "Name is required (max 66 characters)"

    if not validate_email(s[f"{prefix}_email"]):
        errors["email"] = "Please enter a valid email address"

    if not validate_phone(s[f"{prefix}_phone"]):
        errors["phone"] = "Please enter a valid Phone no. (6–12 digits)"

    if vis["importer_name"] and not validate_importer_name(s[f"{prefix}_importer_name"]):
        errors["importer_name"] = "Importer name required (max 50 alphanumeric characters)"

    # UEN is optional – only validate format if non-empty
    if vis["uen"] and s[f"{prefix}_uen"] and not validate_uen(s[f"{prefix}_uen"]):
        errors["uen"] = "UEN must be up to 10 alphanumeric characters"

    return errors

# ──────────────────────────────────────────────
# Reusable inline-error helper
# ──────────────────────────────────────────────

def err(errors: dict, key: str):
    if key in errors:
        st.markdown(
            f"<p style='color:#d32f2f;font-size:0.82rem;margin-top:-8px'>"
            f"⚠ {errors[key]}</p>",
            unsafe_allow_html=True,
        )

# ──────────────────────────────────────────────
# MyInfo autofill badge helper
# ──────────────────────────────────────────────

def sp_badge():
    st.markdown(
        "<span style='background:#0055a5;color:white;border-radius:4px;"
        "padding:2px 8px;font-size:0.72rem;margin-left:4px'>"
        "Retrieved from MyInfo</span>",
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────
# Progress bar
# ──────────────────────────────────────────────

def progress_bar(step=1, total=5):
    pct = step / total
    st.markdown(
        f"""
        <div style='margin-bottom:6px;font-size:0.85rem;color:#555'>
            Step {step} of {total}
        </div>
        <div style='background:#e0e0e0;border-radius:6px;height:8px;margin-bottom:18px'>
            <div style='background:#0055a5;width:{pct*100:.0f}%;height:8px;border-radius:6px'></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────
# Pill-style segmented button (simulated with columns)
# ──────────────────────────────────────────────

def bind_text_widget(prefix: str, logical_suffix: str, widget_suffix: str):
    """Init widget session key from logical field once. Avoids value= + key (breaks on Streamlit Cloud)."""
    wk = f"{prefix}_{widget_suffix}"
    lk = f"{prefix}_{logical_suffix}"
    if wk not in st.session_state:
        v = st.session_state.get(lk)
        st.session_state[wk] = "" if v is None else str(v)


def ensure_myinfo_text_widget(prefix: str, field: str, stamp: int):
    """Bind `{prefix}_{field}_mi{stamp}` from logical `{prefix}_{field}` if unset (MyInfo pre-seeds before rerun)."""
    s = st.session_state
    wk = f"{prefix}_{field}_mi{stamp}"
    lk = f"{prefix}_{field}"
    if wk not in s:
        v = s.get(lk)
        s[wk] = "" if v is None else str(v)


def stabilize_improved_form_state(prefix: str):
    """Improved prototype is always Traveller + NRIC so NRIC/personal widgets always mount."""
    s = st.session_state
    if s.get(f"{prefix}_decl_type") is None:
        s[f"{prefix}_decl_type"] = "Traveller"
    s[f"{prefix}_doc_type"] = "NRIC"


def repair_myinfo_widget_keys(prefix: str):
    """
    Streamlit deletes session_state for a widget if that widget is not executed in a run
    (e.g. lazy tabs on Cloud). Logical fields (sp_name, …) still hold MyInfo data — repopulate
    the versioned widget keys so text_input shows them again.
    """
    s = st.session_state
    if not s.get(f"{prefix}_singpass_used"):
        return
    mis = int(s.get(f"{prefix}_myinfo_stamp") or 0)
    if mis < 1:
        return
    pairs = [
        ("nric", True),
        ("name", False),
        ("email", False),
        ("phone", False),
    ]
    for field, upper in pairs:
        lk = f"{prefix}_{field}"
        wk = f"{prefix}_{field}_mi{mis}"
        lv = s.get(lk)
        if lv is None or str(lv).strip() == "":
            continue
        cur = s.get(wk, "")
        if wk not in s or str(cur).strip() == "":
            s[wk] = str(lv).strip().upper() if upper else str(lv)


def reset_doc_dependent_fields(prefix: str):
    """Clear fields that depend on travel document type when the type changes."""
    s = st.session_state
    s[f"{prefix}_pass_holder"] = None
    s[f"{prefix}_nric"] = ""
    s[f"{prefix}_nric_input"] = ""
    s[f"{prefix}_fin"] = ""
    s[f"{prefix}_fin_input"] = ""
    s[f"{prefix}_passport_no"] = ""
    s[f"{prefix}_passport_no_input"] = ""
    s[f"{prefix}_passport_expiry"] = None
    s[f"{prefix}_nationality"] = ""
    s[f"{prefix}_passport_expiry_input"] = None
    s[f"{prefix}_nationality_input"] = ""


def segmented_buttons(
    label: str,
    options: list,
    state_key: str,
    required: bool = True,
    on_interaction=None,
    on_value_change=None,
):
    """Render pill-style button group; updates st.session_state[state_key]. None = nothing selected (all secondary)."""
    current = st.session_state.get(state_key)
    st.markdown(
        f"<p style='margin-bottom:4px;font-weight:600;font-size:0.9rem'>"
        f"{label}{'<span style=\"color:#d32f2f\"> *</span>' if required else ''}</p>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(options))
    for i, opt in enumerate(options):
        selected = current == opt
        if cols[i].button(
            opt,
            key=f"_btn_{state_key}_{opt}",
            use_container_width=True,
            help=f"Select {opt}",
            type="primary" if selected else "secondary",
        ):
            old = st.session_state.get(state_key)
            st.session_state[state_key] = opt
            if on_value_change and old != opt:
                on_value_change(opt, old)
            if on_interaction:
                on_interaction()
            st.rerun()
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] button {
            border-radius: 20px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────
# Main form renderer
# ──────────────────────────────────────────────

def render_form(prefix: str, with_singpass: bool = False):
    """
    Render the Personal Information form.

    prefix       – unique key prefix for session state (avoids key clashes between tabs)
    with_singpass – whether to show the MyInfo autofill section
    """
    _init_state(prefix)
    s = st.session_state
    if with_singpass:
        stabilize_improved_form_state(prefix)
        repair_myinfo_widget_keys(prefix)

    def record_interaction():
        # Baseline form only: capture time from first click/input to "Next".
        if s.get(f"{prefix}_started_at") is None:
            s[f"{prefix}_started_at"] = time.time()

    def fmt_seconds(sec: float) -> str:
        sec_int = int(sec)
        m = sec_int // 60
        r = sec_int % 60
        return f"{m}m {r:02d}s"

    # ── MyInfo section (Improved tab only) ────────────────────────────────
    if with_singpass:
        st.markdown(
            "<div style='background:#e8f4fd;border:1px solid #90caf9;"
            "border-radius:8px;padding:14px 18px;margin-bottom:18px'>"
            "<p style='margin:0;font-size:0.82rem;color:#0055a5;font-weight:600'>"
            "⚡ Complete this step in under 2 minutes</p>"
            "<p style='margin:4px 0 0;font-size:0.8rem;color:#333'>"
            "In production, travellers would authenticate via MyInfo "
            "(typically by scanning a QR code on mobile), and upon consent, "
            "MyInfo would return their personal details to prefill the form. "
            "In this prototype, we simulate that flow to demonstrate the UX impact.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        col_sp, col_note = st.columns([1, 2])
        with col_sp:
            if st.button("🔐 Retrieve details with MyInfo", use_container_width=True, type="primary"):
                record_interaction()
                mis = s.get(f"{prefix}_myinfo_stamp", 0) + 1
                s[f"{prefix}_myinfo_stamp"] = mis
                s[f"{prefix}_name"] = MOCK_MYINFO["name"]
                s[f"{prefix}_email"] = MOCK_MYINFO["email"]
                s[f"{prefix}_phone"] = MOCK_MYINFO["phone"]
                s[f"{prefix}_nric"] = "T1214619H"
                s[f"{prefix}_doc_type"] = "NRIC"
                # Do not set *_mi{mis} keys here: this run ends before text_input executes, and
                # Streamlit drops session_state for widget keys that never mount in that run.
                s[f"{prefix}_sp_name_autofilled"] = True
                s[f"{prefix}_sp_email_autofilled"] = True
                s[f"{prefix}_sp_phone_autofilled"] = True
                s[f"{prefix}_singpass_used"]       = True
                st.rerun()
        with col_note:
            if s[f"{prefix}_singpass_used"]:
                st.success("Details retrieved. Please verify before continuing.")

        st.markdown("---")

    # ── Baseline: Declaration & Document (no default pill highlight until click) ──
    if not with_singpass:
        with st.container(border=True):
            st.markdown("#### Declaration & Document Type")
            segmented_buttons(
                "Type of Declaration",
                DECLARATION_TYPES,
                f"{prefix}_decl_type",
                on_interaction=record_interaction,
            )
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            def _on_doc_type_change(new, old):
                if old is not None and new != old:
                    reset_doc_dependent_fields(prefix)

            segmented_buttons(
                "Travel Document Type",
                DOC_TYPES,
                f"{prefix}_doc_type",
                on_interaction=record_interaction,
                on_value_change=_on_doc_type_change,
            )

            decl = s[f"{prefix}_decl_type"]
            doc = s[f"{prefix}_doc_type"]
            if decl == "Traveller":
                if doc in ("NRIC", "FIN"):
                    default_ph = "No" if doc == "NRIC" else "Yes"
                    s[f"{prefix}_pass_holder"] = default_ph

                    st.markdown(
                        "<p style='font-weight:600;font-size:0.9rem'>Are you a Singapore pass-holder? "
                        "<span style='color:#d32f2f'>*</span></p>",
                        unsafe_allow_html=True,
                    )
                    # Read-only (not editable); styled like active radios — Streamlit's disabled=True grays the control.
                    yes_on = default_ph == "Yes"
                    no_on = default_ph == "No"
                    accent = "#0055a5"
                    ring_sel = f"border:2px solid {accent};background:#fff;box-shadow:inset 0 0 0 5px {accent}"
                    idle = "border:2px solid #5c5e61;background:#fff;box-shadow:none"
                    st.markdown(
                        f"""
                        <div role="radiogroup" aria-label="Are you a Singapore pass-holder?"
                             style="display:flex;gap:32px;align-items:center;padding:6px 2px 10px;
                             font-size:1rem;color:#31333F;user-select:none">
                            <div style="display:flex;align-items:center;gap:10px">
                                <span aria-hidden="true" style="display:inline-block;width:20px;height:20px;
                                    border-radius:50%;flex-shrink:0;{ring_sel if yes_on else idle}"></span>
                                <span style="font-weight:{'600' if yes_on else '400'};color:{accent if yes_on else '#31333F'}">Yes</span>
                            </div>
                            <div style="display:flex;align-items:center;gap:10px">
                                <span aria-hidden="true" style="display:inline-block;width:20px;height:20px;
                                    border-radius:50%;flex-shrink:0;{ring_sel if no_on else idle}"></span>
                                <span style="font-weight:{'600' if no_on else '400'};color:{accent if no_on else '#31333F'}">No</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        errs_decl_doc = field_errors(prefix, with_singpass)
        err(errs_decl_doc, "decl_type")
        err(errs_decl_doc, "doc_type")

    # ── Section 2: Document Details ───────────────────────────────────────
    vis = visible_fields(prefix, with_singpass)
    if with_singpass:
        repair_myinfo_widget_keys(prefix)
    errors_all = field_errors(prefix, with_singpass)  # compute once for summary; inline shown per field

    with st.container(border=True):
        st.markdown("#### Document Details")

        doc = s[f"{prefix}_doc_type"]
        if doc == "Passport":
            st.warning(
                "If you are a holder of a work permit, employment pass, student pass, "
                "dependent pass or long-term pass issued by the Singapore Government, "
                "kindly input your FIN instead of passport number."
            )

        if vis["period_away"]:
            st.markdown(
                "<p style='font-weight:600;font-size:0.9rem'>Select period away from Singapore. "
                "<span style='color:#d32f2f'>*</span></p>",
                unsafe_allow_html=True,
            )
            current_period = s[f"{prefix}_period_away"]
            period = st.radio(
                "Select period away from Singapore. *",
                options=PERIOD_AWAY_OPTIONS,
                index=PERIOD_AWAY_OPTIONS.index(current_period) if current_period in PERIOD_AWAY_OPTIONS else None,
                horizontal=True,
                label_visibility="collapsed",
                key=f"{prefix}_period_input",
                on_change=record_interaction,
            )
            s[f"{prefix}_period_away"] = period
            err(errors_all, "period_away")

        if vis["nric"]:
            if with_singpass:
                _mis = s.get(f"{prefix}_myinfo_stamp", 0)
                ensure_myinfo_text_widget(prefix, "nric", _mis)
                val = st.text_input(
                    "NRIC *",
                    placeholder="e.g. S1234567D",
                    max_chars=9,
                    key=f"{prefix}_nric_mi{_mis}",
                    on_change=record_interaction,
                )
            else:
                bind_text_widget(prefix, "nric", "nric_input")
                val = st.text_input(
                    "NRIC *",
                    placeholder="e.g. S1234567D",
                    max_chars=9,
                    key=f"{prefix}_nric_input",
                    on_change=record_interaction,
                )
            s[f"{prefix}_nric"] = val.strip().upper()
            err(errors_all, "nric")

        if vis["fin"]:
            bind_text_widget(prefix, "fin", "fin_input")
            val = st.text_input(
                "FIN *",
                placeholder="e.g. F9989472P",
                max_chars=9,
                key=f"{prefix}_fin_input",
                on_change=record_interaction,
            )
            s[f"{prefix}_fin"] = val.strip().upper()
            err(errors_all, "fin")

        if vis["passport_no"]:
            bind_text_widget(prefix, "passport_no", "passport_no_input")
            val = st.text_input(
                "Passport No. *",
                placeholder="Up to 9 alphanumeric characters",
                max_chars=9,
                key=f"{prefix}_passport_no_input",
                on_change=record_interaction,
            )
            s[f"{prefix}_passport_no"] = val.strip().upper()
            err(errors_all, "passport_no")

        if vis["passport_expiry"]:
            today = date.today()
            max_d = today + timedelta(days=365 * 10 + 1)
            current_exp = s[f"{prefix}_passport_expiry"] or today
            exp = st.date_input(
                "Passport Expiry Date *",
                value=current_exp,
                min_value=today,
                max_value=max_d,
                key=f"{prefix}_passport_expiry_input",
                on_change=record_interaction,
            )
            s[f"{prefix}_passport_expiry"] = exp
            err(errors_all, "passport_expiry")

        if vis["nationality"]:
            idx = NATIONALITIES.index(s[f"{prefix}_nationality"]) + 1 if s[f"{prefix}_nationality"] in NATIONALITIES else 0
            nat = st.selectbox(
                "Nationality *",
                options=["— Select nationality —"] + NATIONALITIES,
                index=idx,
                key=f"{prefix}_nationality_input",
                on_change=record_interaction,
            )
            s[f"{prefix}_nationality"] = "" if nat.startswith("—") else nat
            err(errors_all, "nationality")

        if vis["pass_holder"] and get_effective_pass_holder(prefix) is None:
            err(errors_all, "pass_holder")

    # ── Section 3: Personal Details ───────────────────────────────────────
    with st.container(border=True):
        st.markdown("#### Personal Details")

        # Name
        name_label = "Name *"
        if with_singpass and s[f"{prefix}_sp_name_autofilled"]:
            st.markdown(
                "<p style='font-weight:600;font-size:0.9rem'>Name * "
                "<span style='background:#0055a5;color:white;border-radius:4px;"
                "padding:1px 7px;font-size:0.72rem'>Retrieved from MyInfo</span></p>",
                unsafe_allow_html=True,
            )
            name_label = "Name *"
        _mis = s.get(f"{prefix}_myinfo_stamp", 0)
        if with_singpass:
            ensure_myinfo_text_widget(prefix, "name", _mis)
            val = st.text_input(
                name_label,
                max_chars=66,
                key=f"{prefix}_name_mi{_mis}",
                label_visibility="collapsed" if (with_singpass and s[f"{prefix}_sp_name_autofilled"]) else "visible",
                on_change=record_interaction,
            )
        else:
            bind_text_widget(prefix, "name", "name_input")
            val = st.text_input(
                name_label,
                max_chars=66,
                key=f"{prefix}_name_input",
                label_visibility="visible",
                on_change=record_interaction,
            )
        s[f"{prefix}_name"] = val.strip()
        if s[f"{prefix}_name"] and len(s[f"{prefix}_name"]) > 66:
            st.markdown("<p style='color:#d32f2f;font-size:0.82rem'>Name must not exceed 66 characters</p>", unsafe_allow_html=True)
        elif "name" in errors_all and s[f"{prefix}_name"] == "":
            err(errors_all, "name")

        # Email
        if with_singpass and s[f"{prefix}_sp_email_autofilled"]:
            st.markdown(
                "<p style='font-weight:600;font-size:0.9rem'>Email Address * "
                "<span style='background:#0055a5;color:white;border-radius:4px;"
                "padding:1px 7px;font-size:0.72rem'>Retrieved from MyInfo</span></p>",
                unsafe_allow_html=True,
            )
            email_label_vis = "collapsed"
        else:
            email_label_vis = "visible"

        if with_singpass:
            ensure_myinfo_text_widget(prefix, "email", _mis)
            val = st.text_input(
                "Email Address *",
                placeholder="e.g. user@example.com",
                key=f"{prefix}_email_mi{_mis}",
                label_visibility=email_label_vis,
                on_change=record_interaction,
            )
        else:
            bind_text_widget(prefix, "email", "email_input")
            val = st.text_input(
                "Email Address *",
                placeholder="e.g. user@example.com",
                key=f"{prefix}_email_input",
                label_visibility=email_label_vis,
                on_change=record_interaction,
            )
        s[f"{prefix}_email"] = val.strip()
        err(errors_all, "email")

        # Phone
        if with_singpass and s[f"{prefix}_sp_phone_autofilled"]:
            st.markdown(
                "<p style='font-weight:600;font-size:0.9rem'>Phone Number * "
                "<span style='background:#0055a5;color:white;border-radius:4px;"
                "padding:1px 7px;font-size:0.72rem'>Retrieved from MyInfo</span></p>",
                unsafe_allow_html=True,
            )
            phone_label_vis = "collapsed"
        else:
            phone_label_vis = "visible"

        if with_singpass:
            ensure_myinfo_text_widget(prefix, "phone", _mis)
            val = st.text_input(
                "Phone Number *",
                placeholder="6–12 digits",
                key=f"{prefix}_phone_mi{_mis}",
                label_visibility=phone_label_vis,
                on_change=record_interaction,
            )
        else:
            bind_text_widget(prefix, "phone", "phone_input")
            val = st.text_input(
                "Phone Number *",
                placeholder="6–12 digits",
                key=f"{prefix}_phone_input",
                label_visibility=phone_label_vis,
                on_change=record_interaction,
            )
        s[f"{prefix}_phone"] = val.strip()
        err(errors_all, "phone")

    # ── Section 4: Commercial Fields ──────────────────────────────────────
    if vis["importer_name"] or vis["uen"]:
        with st.container(border=True):
            st.markdown("#### Commercial Details")
            if vis["importer_name"]:
                bind_text_widget(prefix, "importer_name", "importer_name_input")
                val = st.text_input(
                    "Singapore Importer Name *",
                    max_chars=50,
                    key=f"{prefix}_importer_name_input",
                )
                s[f"{prefix}_importer_name"] = val.strip()
                err(errors_all, "importer_name")

            if vis["uen"]:
                bind_text_widget(prefix, "uen", "uen_input")
                val = st.text_input(
                    "UEN (optional)",
                    max_chars=10,
                    key=f"{prefix}_uen_input",
                )
                s[f"{prefix}_uen"] = val.strip().upper()
                err(errors_all, "uen")

    # ── Validation Summary ────────────────────────────────────────────────
    errors_now = field_errors(prefix, with_singpass)   # re-evaluate after any updates

    has_started = s.get(f"{prefix}_started_at") is not None
    next_clicked = bool(s.get(f"{prefix}_next_clicked"))

    # Avoid showing red validation feedback on initial load.
    if errors_now and (has_started or next_clicked):
        with st.expander("⚠ Please fix the following before continuing", expanded=True):
            for k, msg in errors_now.items():
                st.markdown(f"- {msg}")

    # ── Navigation Buttons ────────────────────────────────────────────────
    st.markdown("---")
    col_back, col_spacer, col_next = st.columns([1, 3, 1])
    with col_back:
        st.button("← Back", key=f"{prefix}_back_btn", use_container_width=True)
    with col_next:
        next_disabled = bool(errors_now)
        if st.button(
            "Next →",
            key=f"{prefix}_next_btn",
            disabled=next_disabled,
            use_container_width=True,
            type="primary",
        ):
            record_interaction()
            elapsed = time.time() - s[f"{prefix}_started_at"]
            s[f"{prefix}_time_to_next_sec"] = elapsed
            s[f"{prefix}_next_clicked"] = True
            st.success(
                f"Time to complete: {fmt_seconds(elapsed)} (from first interaction). "
                "Proceeding to Step 2 (not implemented in prototype)."
            )

    if next_disabled:
        st.caption("Complete all required fields to enable Next.")

# ──────────────────────────────────────────────
# Page config & layout
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="Customs@SG – Personal Information",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Global CSS
st.markdown(
    """
    <style>
        .block-container { max-width: 720px; }
        .stButton > button {
            border-radius: 20px;
        }
        .stButton > button[kind="primary"] {
            background-color: #0055a5;
            border-color: #0055a5;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] select {
            border-radius: 6px;
        }
        h4 { margin-top: 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Page Header ────────────────────────────────────────────────────────────
st.markdown(
    "<h2 style='color:#0055a5;margin-bottom:2px'>Customs@SG – Personal Information</h2>",
    unsafe_allow_html=True,
)
st.caption("Singapore Customs | Traveller Declaration Portal  |  *Prototype – synthetic data only*")
st.markdown("<hr style='margin:8px 0 16px'>", unsafe_allow_html=True)
progress_bar(step=1, total=5)

# ── Form variant (radio, not tabs): only one form runs per rerun. Streamlit deletes widget
#    session_state for widgets that are not instantiated; lazy tabs on Cloud often skip the
#    hidden tab, wiping sp_* keys while sp_name / sp_nric still hold MyInfo data — fields stayed empty.
FORM_LABEL_BASE = "📋  Baseline Form"
FORM_LABEL_IMPROVED = "⚡  Improved Form with MyInfo Autofill"
st.markdown("##### Prototype variant")
variant = st.radio(
    "Prototype variant",
    [FORM_LABEL_BASE, FORM_LABEL_IMPROVED],
    horizontal=True,
    label_visibility="collapsed",
    key="_form_variant_pick",
)
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

if variant == FORM_LABEL_BASE:
    render_form(prefix="base", with_singpass=False)
else:
    render_form(prefix="sp", with_singpass=True)
