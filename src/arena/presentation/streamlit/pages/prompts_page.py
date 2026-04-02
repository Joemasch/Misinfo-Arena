"""
Prompts Page for Misinformation Arena v2

Allows users to view, edit, and persist custom system prompts for the
Spreader, Debunker, and Judge agents. Supports a consolidated Prompt Library
for saving multiple variants and activating one per agent.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from arena.app_config import SPREADER_SYSTEM_PROMPT, DEBUNKER_SYSTEM_PROMPT, PROMPTS_PATH
from arena.io.prompts_store import load_prompts_file, save_prompts_file
from arena.prompts.judge_static_prompt import (
    get_judge_static_prompt,
    get_judge_static_prompt_version,
)
from arena.prompts.prompt_library import (
    add_blank_prompt_entry,
    get_agent_prompt_entries,
    get_active_prompt_id,
    set_active_prompt_id,
    update_prompts_file_merge,
    update_prompt_entry,
    delete_prompt_entry,
)

AGENT_LABELS = {"spreader": "Spreader", "debunker": "Debunker", "judge": "Judge"}
SS_KEYS = {"spreader": "spreader_prompt", "debunker": "debunker_prompt", "judge": "judge_static_prompt"}


def _fmt_ts(iso: str) -> str:
    """Format ISO timestamp to human-readable string, e.g. 'Mar 31, 2026 at 14:22'."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%b %-d, %Y at %H:%M")
    except Exception:
        return iso  # fallback to raw if unparseable


def _render_prompt_library_section(agent_type: str):
    """Render the prompt library block for one agent type."""
    entries = get_agent_prompt_entries(agent_type)
    active_id = get_active_prompt_id(agent_type)
    label = AGENT_LABELS[agent_type]

    for idx, e in enumerate(entries):
        eid = e.get("id", "")
        if not eid:
            continue

        is_active = eid == active_id
        prompt_key = f"lib_prompt_{agent_type}_{eid}"
        notes_key = f"lib_notes_{agent_type}_{eid}"
        name_key = f"lib_name_{agent_type}_{eid}"

        # Initialize session_state from entry if not yet set (handles first load after add)
        if prompt_key not in st.session_state:
            st.session_state[prompt_key] = e.get("prompt_text", "")
        if notes_key not in st.session_state:
            st.session_state[notes_key] = e.get("notes", "")
        if name_key not in st.session_state:
            st.session_state[name_key] = e.get("name", "Untitled")

        is_research_default = bool(e.get("research_default", False))

        name_row = st.columns([3, 1, 1])
        with name_row[0]:
            st.text_input("Name", value=st.session_state.get(name_key, e.get("name", "Untitled")), key=name_key, label_visibility="collapsed", placeholder="Prompt name")
        with name_row[1]:
            if is_research_default:
                st.markdown(
                    '<span style="display:inline-block;font-size:0.7rem;font-weight:700;'
                    'text-transform:uppercase;letter-spacing:0.07em;padding:0.15rem 0.5rem;'
                    'background:rgba(99,102,241,0.12);color:#4338ca;border-radius:999px;">'
                    '🔬 Research Default</span>',
                    unsafe_allow_html=True,
                )
        with name_row[2]:
            if is_active:
                st.success("✓ Active")
        st.caption(f"`{eid}`  ·  version: {e.get('base_version', '—')}")

        col_prompt, col_notes, col_actions = st.columns([4, 2, 1])
        with col_prompt:
            st.text_area(
                "Prompt",
                value=st.session_state.get(prompt_key, e.get("prompt_text", "")),
                height=180,
                key=prompt_key,
            )
        with col_notes:
            st.text_area(
                "Notes / Performance Observations",
                value=st.session_state.get(notes_key, e.get("notes", "")),
                height=180,
                key=notes_key,
            )
        with col_actions:
            if st.button("Apply Prompt", key=f"apply_{agent_type}_{eid}", type="primary" if is_active else "secondary"):
                prompt_text = st.session_state.get(prompt_key, "")
                update_prompt_entry(
                    agent_type,
                    eid,
                    {
                        "name": (st.session_state.get(name_key, "") or "").strip() or "Untitled",
                        "prompt_text": prompt_text,
                        "notes": st.session_state.get(notes_key, ""),
                    },
                )
                set_active_prompt_id(agent_type, eid, prompt_text)
                # Stage the new prompt — applied before widget creation on next run
                st.session_state[f"_pending_{SS_KEYS[agent_type]}"] = prompt_text
                # Use the name from session state (reflects any rename the user just made)
                applied_name = (st.session_state.get(name_key, "") or "").strip() or "Untitled"
                st.toast(f"Applied: {applied_name}", icon="✅")
                st.rerun()

            if st.button("Save Changes", key=f"save_{agent_type}_{eid}"):
                update_prompt_entry(
                    agent_type,
                    eid,
                    {
                        "name": (st.session_state.get(name_key, "") or "").strip() or "Untitled",
                        "prompt_text": st.session_state.get(prompt_key, ""),
                        "notes": st.session_state.get(notes_key, ""),
                    },
                )
                st.toast("Saved", icon="✅")
                st.rerun()

            if is_research_default:
                st.caption("Research defaults cannot be deleted")
            elif not is_active:
                if st.button("Delete", key=f"del_{agent_type}_{eid}"):
                    delete_prompt_entry(agent_type, eid)
                    for k in [prompt_key, notes_key, name_key]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.toast("Deleted", icon="🗑️")
                    st.rerun()
            else:
                st.caption("(Active prompts cannot be deleted)")

        ts = _fmt_ts(e.get("updated_at", ""))
        if ts:
            st.caption(f"Last saved: {ts}")
        st.divider()

    if entries:
        if st.button(f"➕ Add Another {label} Prompt", key=f"add_{agent_type}"):
            add_blank_prompt_entry(agent_type)
            st.toast(f"Added new {label} prompt", icon="➕")
            st.rerun()
    else:
        st.info(
            f"No saved {label.lower()} prompts yet. "
            f"Click below to add your first variant — you can name it, write the prompt, "
            f"add performance notes, and apply it to the active runtime."
        )
        if st.button(f"➕ Add First {label} Prompt", key=f"add_{agent_type}"):
            add_blank_prompt_entry(agent_type)
            st.toast(f"Added new {label} prompt", icon="➕")
            st.rerun()


def render_prompts_page():
    """
    Render the Prompts page for editing system prompts and managing prompt library.
    """
    st.header("🎭 Prompts")
    st.caption("Edit system prompts for each agent. The Prompt Library below lets you save variants and experiment.")

    # Flush any staged prompt values before widgets are instantiated
    for _ss_key in SS_KEYS.values():
        _pending = f"_pending_{_ss_key}"
        if _pending in st.session_state:
            st.session_state[_ss_key] = st.session_state.pop(_pending)

    default_spreader = SPREADER_SYSTEM_PROMPT
    default_debunker = DEBUNKER_SYSTEM_PROMPT
    default_judge = get_judge_static_prompt()

    current_spreader = st.session_state.get("spreader_prompt", default_spreader)
    current_debunker = st.session_state.get("debunker_prompt", default_debunker)
    current_judge = st.session_state.get("judge_static_prompt", default_judge)

    # ===================================================================
    # CURRENT ACTIVE PROMPTS (top section)
    # ===================================================================
    st.subheader("Current Active Prompts")
    st.caption("These prompts are used at runtime. Edit here or apply a saved prompt from the library below.")

    # Show which library variant is active for each agent (if any)
    active_info = []
    for agent_type, label in AGENT_LABELS.items():
        active_id = get_active_prompt_id(agent_type)
        if active_id:
            entries = get_agent_prompt_entries(agent_type)
            match = next((e for e in entries if e.get("id") == active_id), None)
            if match:
                active_info.append(f"**{label}**: {match.get('name', 'Untitled')}")
    if active_info:
        st.success("Library variants active — " + " · ".join(active_info))
    else:
        st.info("No library variants applied — using prompts as edited above.")

    st.markdown("**Spreader**")
    st.text_area(
        "Spreader system prompt",
        value=current_spreader,
        height=220,
        help="Instructions for the misinformation spreader agent",
        key="spreader_prompt",
        label_visibility="collapsed",
    )
    st.markdown("**Debunker**")
    st.text_area(
        "Debunker system prompt",
        value=current_debunker,
        height=220,
        help="Instructions for the fact-checker debunker agent",
        key="debunker_prompt",
        label_visibility="collapsed",
    )
    st.markdown("**Judge Prompt (Static)**")
    st.caption(f"Version: {get_judge_static_prompt_version()} — Include `<TRANSCRIPT_PLACEHOLDER>` for transcript insertion.")
    st.text_area(
        "Judge static prompt",
        value=current_judge,
        height=340,
        help="Judge rubric and evaluation instructions. Transcript inserted at <TRANSCRIPT_PLACEHOLDER>.",
        key="judge_static_prompt",
        label_visibility="collapsed",
    )

    # ---- Global actions ----
    spreader_modified = (st.session_state.get("spreader_prompt") or "").strip() != default_spreader.strip()
    debunker_modified = (st.session_state.get("debunker_prompt") or "").strip() != default_debunker.strip()
    judge_modified = (st.session_state.get("judge_static_prompt") or "").strip() != default_judge.strip()
    if spreader_modified or debunker_modified or judge_modified:
        st.warning("⚠️ Custom prompts active — prompts differ from research defaults. Each run snapshots exactly what is shown above.")
    else:
        st.success("✅ IME507 research-grounded prompts active.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Apply", type="primary", help="Save current prompts to disk"):
            try:
                data = load_prompts_file()
                data["spreader_prompt"]    = st.session_state.get("spreader_prompt", "")
                data["debunker_prompt"]    = st.session_state.get("debunker_prompt", "")
                data["judge_static_prompt"] = st.session_state.get("judge_static_prompt", "")
                save_prompts_file(data)
                st.toast("Prompts applied and saved.", icon="✅")
            except Exception as save_err:
                st.error(f"Failed to save prompts to disk: {save_err}. Prompts are active for this session only.")
            st.rerun()
    with col2:
        if st.button("Reset to defaults", help="Restore original default prompts"):
            # Stage values — applied before widgets render on the next run
            st.session_state["_pending_spreader_prompt"] = default_spreader
            st.session_state["_pending_debunker_prompt"] = default_debunker
            st.session_state["_pending_judge_static_prompt"] = default_judge
            update_prompts_file_merge({
                "spreader_prompt": default_spreader,
                "debunker_prompt": default_debunker,
                "judge_static_prompt": default_judge,
                "active_spreader_id": "",
                "active_debunker_id": "",
                "active_judge_id": "",
            })
            st.toast("Prompts reset to defaults.", icon="♻️")
            st.rerun()

    st.divider()

    # ===================================================================
    # PROMPT LIBRARY (consolidated section)
    # ===================================================================
    st.subheader("📚 Prompt Library")
    st.caption(
        "Save prompt variants for experiments. Add blocks, edit prompt text and notes, "
        "then click **Apply Prompt** to make that variant the active runtime prompt."
    )

    st.markdown("---")
    st.markdown("**Spreader Prompt Library**")
    _render_prompt_library_section("spreader")

    st.markdown("---")
    st.markdown("**Debunker Prompt Library**")
    _render_prompt_library_section("debunker")

    st.markdown("---")
    st.markdown("**Judge Prompt Library**")
    _render_prompt_library_section("judge")

    st.divider()
    st.subheader("📋 How This Works")
    st.markdown("""
    **Current Active Prompts**: The top editors show the prompts used at runtime. Edit here or apply a saved prompt from the library.

    **Prompt Library**: Add and manage prompt variants. Each block has prompt text, notes for performance observations, and an **Apply Prompt** button to make it active.

    **Persistence**: Prompts are saved to `prompts.json`. Saved variants are stored in `prompt_library.json`.

    **Snapshot Capture**: Every run records the exact prompts used for reproducibility.
    """)
    if PROMPTS_PATH.exists():
        st.info(f"💾 Prompts loaded from {PROMPTS_PATH}")
    else:
        st.info("📄 Using built-in default prompts (no prompts.json found)")
