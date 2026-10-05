# Run via local-signoff.ps1 -DraftEditorOnly. Only creates its own fictional draft.
Invoke-JavaScript "document.querySelector('.new-chat').click(); true" | Out-Null
Wait-JavaScript "document.querySelectorAll('.template-choice').length === 3" 'template picker'
Invoke-JavaScript "document.querySelector('[data-template-id=generic-role]').click(); true" | Out-Null
Wait-JavaScript "document.querySelector('.draft-sidebar [data-field-state=unanswered]') !== null" 'blank draft'
Set-InputAndSubmit "textarea[aria-label='Conversation message']" 'Company name: Example Circuits; Company location: Durban; Job title: Simple Form Check Engineer; Role description: Design and test PCB circuits; Work arrangement: on-site; Location: Durban; Skills: circuit design is required; No experience required; No degree needed. Working hours: 40 hours a week preferred. Applications close on 30 November 2026.'
Wait-JavaScript "document.querySelector('[data-field-key=job_title] input[name=value]')?.value.includes('Simple Form Check Engineer') && !document.querySelector('.typing')" 'captured role' 45
if (-not (Invoke-JavaScript "document.querySelector('[data-field-key=closing_date] input[name=value]')?.value === '2026-11-30'")) { throw 'Chat closing date was not captured' }
if (Invoke-JavaScript "document.querySelector('.draft-sidebar .draft-state, .draft-sidebar select, .draft-sidebar textarea') !== null") { throw 'Extra field controls remain' }
if (Invoke-JavaScript "document.querySelector('[data-field-key=working_hours] p:not([hidden])') !== null") { throw 'Working hours still has duplicate descriptions' }
Invoke-JavaScript "[...document.querySelectorAll('.template-draft button')].find(b => b.textContent === 'Add a field').click(); true" | Out-Null
Wait-JavaScript "document.querySelector('.draft-new-field') !== null" 'two-input add form'
Invoke-JavaScript @'
(async () => {
  for (const [name, value] of [['label','PCB soldering'], ['value','Must solder pcb compnents safly']]) {
    const input = document.querySelector('.draft-new-field [name=' + name + ']');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', {bubbles:true}));
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  // Label and value save automatically after typing pauses.
  return true;
})()
'@ | Out-Null
Wait-JavaScript "document.querySelector('[data-field-key=pcb_soldering]')?.dataset.fieldState === 'confirmed' && !document.querySelector('.draft-new-field')" 'saved added field' 45
if (-not (Invoke-JavaScript "document.querySelector('.template-draft [role=status]')?.textContent.includes('polished')")) { throw 'AI form polishing did not succeed' }
if (Invoke-JavaScript "document.querySelector('[data-field-key=pcb_soldering] input[name=value]').value.includes('compnents')") { throw 'Misspelled value was not polished' }
function Set-DraftValue([string]$key, [string]$value) {
    $keyJson = $key | ConvertTo-Json -Compress
    $valueJson = $value | ConvertTo-Json -Compress
    Invoke-JavaScript @"
(async () => {
  const input = document.querySelector('[data-field-key=' + $keyJson + '] input[name=value]');
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, $valueJson);
  input.dispatchEvent(new Event('input', {bubbles:true}));
  await new Promise(resolve => setTimeout(resolve, 0));
  if (!document.querySelector('[aria-label="Conversation message"]').disabled) throw new Error('Chat remains editable during a form edit');
  // The edit saves automatically; do not click Save or submit the form.
  return true;
})()
"@ | Out-Null
}
# Edit directly in the visible input, without opening a separate editor.
Set-DraftValue 'pcb_soldering' 'Must solder and inspect PCB joints safely'
Wait-JavaScript "document.querySelector('[data-field-key=pcb_soldering] input[name=value]')?.value.toLowerCase().includes('inspect') && !document.querySelector('[data-field-key=pcb_soldering] input[name=label]')" 'inline edit' 45
Set-DraftValue 'closing_date' '2026-12-31'
Wait-JavaScript "document.querySelector('[data-field-key=closing_date] input[name=value]')?.value === '2026-12-31' && !document.querySelector('[data-field-key=closing_date] input[name=label]')" 'date picker save'
Invoke-JavaScript "document.querySelector('[data-field-key=tools] button[aria-label^=Remove]').click(); true" | Out-Null
Wait-JavaScript "!document.querySelector('[data-field-key=tools]') && !document.querySelector('.typing')" 'removed suggestion'
Invoke-JavaScript "[...document.querySelectorAll('.template-draft > button')].find(b => b.textContent === 'Done').click(); true" | Out-Null
Wait-JavaScript "document.querySelector('.publish-bar') !== null && !document.querySelector('.typing')" 'Done and explicit Publish'
Invoke-JavaScript "document.querySelector('[data-field-key=working_hours]').scrollIntoView({block:'center',behavior:'instant'}); true" | Out-Null
Save-Screenshot 'simple-fields-desktop.png'
Invoke-JavaScript 'window.__draftEditorReload = true; true' | Out-Null
Invoke-Cdp 'Page.reload' | Out-Null
Wait-JavaScript "!window.__draftEditorReload && document.querySelector('[data-field-key=closing_date] input[name=value]')?.value === '2026-12-31'" 'saved date after reload'
Set-Viewport 390 760 $true
Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" 'closed phone menu'
Invoke-JavaScript "document.querySelector('[data-field-key=working_hours]').scrollIntoView({block:'center',behavior:'instant'}); true" | Out-Null
Save-Screenshot 'simple-fields-phone.png'
if (Invoke-JavaScript "document.documentElement.scrollWidth > innerWidth || document.querySelector('.error-notice, .draft-error') !== null") { throw 'Form error or phone overflow' }
Write-Output 'Simple form browser check passed: one label/value per row, real Gemini chat date and polishing, inline edits, date picker, CRUD icons, Done, reload and phone layout. Fictional draft remains unpublished.'
Write-Output "Screenshots: $OutputDirectory"
