# 🎨 Valhalla V2 Design Audit Report

**Date**: Sun Jan  4 11:16:21 HST 2026

---

## Mission Control
**Summary**: The Streamlit dashboard has a good foundation, but improvements can be made to visual hierarchy, spacing, and error handling for a better user experience. The 'Mission Control' theme is present but not fully realized. Accessibility considerations are also lacking.

### Critical Issues
- 🟠 **[hierarchy]**: The 'Mission Briefing' subheader could be visually separated more from the title.  The visual weight is too similar, making it harder to quickly scan the page.
  - *Fix*: Increase the margin above the 'Mission Briefing' subheader and consider using a divider above and below.  Increase the font size of the main title to provide greater contrast.
- 🟠 **[spacing]**: The 'Execute Mission' button is too close to the 'Mission Briefing' text area, making it feel cramped.
  - *Fix*: Increase the margin-top between the text area and the columns containing the button.  Consider adding a small gap between the two columns too.
- 🟠 **[ux]**: The error message `❌ Mission failed: {st.session_state['mission_error']}` could be more user-friendly. It directly displays the technical error message which might not be helpful to the user.
  - *Fix*: Provide a more descriptive error message.  If the error is technical, log the full error for debugging purposes, but display a simplified message to the user.  Consider including a 'Contact Support' link if the error is unresolvable.
- 🟡 **[color]**: The color coding of the Sentiment score is good, but the markdown solution isn't ideal and might lack contrast. 
  - *Fix*: Use `st.progress` with custom styling to create a more visually clear sentiment indicator.  Alternatively, explore Streamlit's theme options for a more consistent color palette across the app.
- 🟠 **[layout]**: The 'Live Telemetry' metrics could be better aligned. The titles don't align visually with the values.
  - *Fix*: Explore using `st.columns` with `use_container_width=True` if it's not already being applied to the top-level columns.  Consider using a single row with slightly larger columns if the metrics are more important. Use `st.caption` below the metric for clarity and alignment.

### Quick Wins
- ✨ Increase margin-top between text area and Execute Mission button
- ✨ Provide multiple short examples in the Mission Briefing placeholder.
- ✨ Simplify error messages displayed to the user.

---

## The Hangar
**Summary**: The Hangar mode provides a useful interface for regression testing and skill configuration. However, the layout could be refined for better visual hierarchy, improved information presentation, and enhanced user experience. Several elements can be tweaked to increase clarity and discoverability.

### Critical Issues
- 🟠 **[hierarchy]**: The page title and subheaders are visually similar, making it difficult to quickly scan and understand the different sections. The subheaders blend in too much.
  - *Fix*: Use a larger font size or a more visually distinct style for the page title. For subheaders, consider a different font weight or adding a visual divider before them. For example: `st.title('🛠️ The Hangar', anchor='top')` and using a styled `st.markdown` for subheaders such as `st.markdown('<h2 style="font-size: 1.5em; font-weight: bold;">🧪 Regression Suite</h2>', unsafe_allow_html=True)`.
- 🟠 **[layout]**: The regression suite button has a large container width which isn't necessary and visually dominates the regression metrics that follow.
  - *Fix*: Reduce the width allocation for the button column. Change `col1, col2 = st.columns([1, 3])` to something like `col1, col2 = st.columns([0.5, 3.5])` to give more space to the regression metrics and make the button less visually dominant.
- 🟠 **[ux]**: The individual test results are presented as JSON within expanders. This is functional, but less user-friendly for quickly understanding the results. Difficult to parse and scan results quickly
  - *Fix*: Consider displaying the key fields from the `r` dictionary (e.g., input, expected output, actual output, error message) in a more structured way, perhaps as a table or using `st.write` with styled markdown.  This would make the results more easily digestible. A simplified view for quick understanding could be shown on the main page, with an option to view the full JSON in the expander.
- 🟡 **[spacing]**: There isn't enough space after the summary metrics and before the 'Delta Analysis' section, causing visual crowding.
  - *Fix*: Add an extra `st.markdown('---')` or `st.empty().write('')` to create more visual separation.
- 🟠 **[ux]**: The 'Editing coming soon' caption is ambiguous and doesn't provide a timeline. This can lead to user frustration.
  - *Fix*: Either implement the editing feature or change the caption to be more specific about the lack of editing capabilities. For example, 'Editing is not currently supported. Please modify skill files directly.'

### Quick Wins
- ✨ Add extra spacing after summary metrics.
- ✨ Update the 'Editing coming soon' caption to be more informative about the current limitations.
- ✨ Make skill selectbox width smaller.

---

## System Architecture
**Summary**: The dashboard provides a good overview of the system architecture using status indicators. However, the visual presentation can be improved for better clarity, user experience, and accessibility. There are opportunities to enhance visual hierarchy, spacing, and provide more informative status messages.

### Critical Issues
- 🟠 **[hierarchy]**: The subheaders are not distinct enough from the surrounding text, making it slightly difficult to scan and understand the information hierarchy at a glance. The emojis are a nice touch but doesn't resolve the issue by itself.
  - *Fix*: Increase the font size of the subheaders and add a subtle background color or border to visually separate them from the content. Consider using `st.header` instead of `st.subheader` or combining with some HTML/CSS styling.
- 🟠 **[spacing]**: The horizontal rules ('---') are functional but visually blend in. They don't provide much visual separation between sections.
  - *Fix*: Increase the spacing above and below the horizontal rules or replace them with a more prominent visual separator like a colored line or divider.  `st.markdown('<hr style="border:1px solid grey;"/>', unsafe_allow_html=True)`
- 🟡 **[color]**: The default green and red color scheme is standard but can be made more accessible and informative.  The green/red color combination isn't ideal for users with colorblindness.
  - *Fix*: Consider adding icons (in addition to colors) to the success and error messages for better visual distinction. Also, explore alternative colorblind-friendly color palettes. For example, use a lighter shade of green for success and a more orange/yellow color for warnings/errors. Use streamlit's theme customization to globally apply the changes.
- 🟠 **[ux]**: The `RunScore Store Locked` message doesn't clearly convey the *reason* for being locked. Is it locked for writing? For Reading? Providing a better explanation improves usability
  - *Fix*: Clarify the meaning of 'locked.' For example: 'Read-Only - No New Scores being Written' or 'In Transaction - No Access Possible'.  A short tooltip would also be beneficial to explain further.
- 🟡 **[ux]**: The `st.info` usage is good, but the bolded 'NO WRITE AUTHORITY' could be visually emphasized further.
  - *Fix*: Use a stronger visual cue, such as a background color or a different font color, for the bolded text. `st.info('ℹ️ Agents in this zone have <span style="color: red; font-weight: bold;">NO WRITE AUTHORITY</span>. Codebase modification is impossible.', unsafe_allow_html=True)`

### Quick Wins
- ✨ Increase spacing above and below horizontal rules.
- ✨ Add icons to success/error messages to supplement color coding.
- ✨ Clarify the 'RunScore Store Locked' message.

---

## Polymarket Scanner
**Summary**: The Streamlit dashboard provides a functional Polymarket scanner with customizable filters and opportunity display. However, several UI/UX improvements can enhance usability, readability, and visual appeal. The structure is generally sound, but refining spacing, visual hierarchy, and user feedback mechanisms will significantly improve the experience.

### Critical Issues
- 🟠 **[layout]**: The arrangement of controls in columns feels somewhat arbitrary.  'Auto-refresh' being in the last column doesn't feel logically connected to the other filter settings.
  - *Fix*: Consider grouping related controls together. For example, place 'Auto-refresh' near the 'Scan Markets' button. Perhaps consolidate `Max Hours` and `Min Certainty` into the same columns as they are the primary search parameters.
- 🟠 **[spacing]**: The spacing between the title/subtitle and the filter section is inconsistent with the spacing within the filter section itself, making the title less strongly associated with the filter controls.
  - *Fix*: Increase the spacing after the title/subtitle to visually separate the explanatory text from the filtering section using `st.markdown('<br><br>')` or simply adding extra empty lines in the code.
- 🟡 **[ux]**: The 'Auto-refresh (5 min)' label doesn't provide sufficient feedback about when the last refresh occurred.
  - *Fix*: Add a timestamp indicating the last refresh time.  Use `datetime.datetime.now()` to get the time, then update the streamlit component using `st.experimental_rerun()` in conjunction with setting a `st.session_state` variable.
- 🟠 **[ux]**: The scan button is placed before the opportunities are displayed. When auto-refresh is enabled the button is pointless and occupies space.
  - *Fix*: Conditionally render the scan button only if auto-refresh is not enabled.  This will reduce clutter.
- 🟠 **[hierarchy]**: The information in the expander header feels a bit crammed. It's difficult to quickly parse the most important information.
  - *Fix*: Re-order and emphasize the key elements: 'Urgency Color | APR | Time Remaining | Question'. Increase the font size of the APR and time remaining.

### Quick Wins
- ✨ Add extra spacing below the title to better separate from filters
- ✨ Reorder opportunity expander header information for clearer readability.
- ✨ Change link text to be more descriptive for accessibility.

---

## Content Library
**Summary**: The Content Library mode has a good structure with clear sections for adding, browsing, and managing content. However, some visual hierarchy and UX improvements can make it more user-friendly and efficient.

### Critical Issues
- 🟠 **[layout]**: The four metric columns are visually dense and their placement isn't very logical. The order of the metrics isn't the most intuitive.
  - *Fix*: Consider reordering metrics to be more logical (Total -> Read -> Unread -> Action Items).  Alternatively, a small chart or progress bar for Read vs Unread can be used instead to reduce visual clutter.
- 🟠 **[ux]**: The 'Ingest' button is visually small in comparison to the very wide URL input, causing a visual imbalance and making it less prominent.
  - *Fix*: Use `st.columns` with appropriate ratios to better balance the URL input and the button.  Consider using `use_container_width=True` for the button. Also, provide visual feedback on successful ingestion, preferably at the top of the page, like with `st.toast`.
- 🟡 **[spacing]**: Too many horizontal rules (`st.markdown('---')`) can create visual fragmentation and clutter.  The visual separation can be enhanced with more subtle techniques.
  - *Fix*: Reduce the number of horizontal rules. Use more spacing (`st.empty().write('')`) or subtle background colors for sections to visually separate content instead.
- 🟠 **[ux]**: The expander title combines status icon, title, relevance bar, and relevance percentage which can feel crowded, particularly with longer titles.
  - *Fix*: Move the relevance bar and percentage to the body of the expander. This will declutter the title and improve scannability. Consider adding the title to the expander body as well, to ensure the long titles are properly visible when collapsed.
- 🟠 **[ux]**: Action items are listed without a clear visual separation from other content details, making them easily missed.
  - *Fix*: Enclose action items in a `st.info` box or use a bulleted list with a distinct icon for each action item for visual prominence. Also, consider using a more actionable label than just the `ActionType` value (e.g., `File a bug` instead of `BUG`).

### Quick Wins
- ✨ Reorder metrics in the metric columns for better flow.
- ✨ Use `st.link_button` for the 'Open URL' button.
- ✨ Use a more prominent warning message and a call to action when no content is found.

---

## Advisor Chat
**Summary**: The Advisor Chat interface has a good structure and functionality, but several areas can be improved for visual clarity, user experience, and accessibility. The main areas of concern involve visual hierarchy within suggestion cards, spacing issues, and providing better feedback to the user.

### Critical Issues
- 🟠 **[layout]**: The Priority selectbox within the Action Suggestions card is placed directly next to the description and badge, making it visually cramped and not easily discoverable. It blends in with the other elements.
  - *Fix*: Move the Priority selectbox above the action description, and give it a clear label like 'Set New Priority'. This will improve discoverability and create a better visual separation. Consider using a Streamlit form for better organization within each action item.

```python
with st.container(): # Wrap each action item
    new_priority = st.selectbox(
        "Set New Priority",
        [1, 2, 3, 4, 5],
        index=priority - 1,
        key=f"action_prio_{idx}_{action.get('description', '')[:15]}",
    )
    st.markdown(f"{badge} **P{priority}**: {action.get('description', '')}")
    st.caption(f"💡 {action.get('reasoning', '')}")
```
- 🟠 **[spacing]**: The accept/reject buttons within the Category Suggestions Card, and Add Task button within Action Suggestions card are too close to the content. This reduces visual separation and makes the interface feel cramped.
  - *Fix*: Add margin around the buttons using CSS. For instance, inject CSS via st.markdown:

```python
st.markdown(
    """
    <style>
    div.stButton > button:first-child {
        margin: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
```
- 🟠 **[ux]**: When an action is added to the Planner, the feedback provided is just a toast. This feedback can be easily missed by the user. No link back to planner is provided to further enhance user experience. The added task id is useful, but not displayed clearly within the toast.
  - *Fix*: Instead of just a toast, display a success message using st.success with a more prominent display of the task ID and a button that links directly to the created task in the Planner if possible (assuming the Planner has accessible URLs).

```python
if "error" not in result:
    task_id = result.get('task', {}).get('id', '')
    st.success(f"✅ Task created with ID: {task_id}")
else:
    st.error(result["error"])
```
- 🟠 **[hierarchy]**: The visual distinction between the 'current' and 'suggested' categories in the Category Suggestions card could be improved. They are currently both displayed using bold text, which doesn't create a clear visual hierarchy.
  - *Fix*: Use different styling to differentiate them. For example, you could use a different color or background color for the suggested category to highlight it as the new option. Using the `st.info` or `st.success` (for positive suggestions) helps to highlight it even further.

```python
st.markdown(f"**{current}** → {st.info(f'**{suggested}**')}")
```
- 🟡 **[ux]**: Content titles longer than 60 characters are truncated with '...'. While functional, this makes it difficult to fully distinguish between similar titles.
  - *Fix*: Consider using a tooltip or hover effect to display the full content title when the user hovers over the truncated title in the selectbox.

Alternatively, increase the truncation limit or implement a more sophisticated truncation method that preserves more context.

### Quick Wins
- ✨ Add margin to the accept/reject buttons using CSS.
- ✨ Use st.info to highlight suggested categories.
- ✨ Add text labels to the priority badges.

---