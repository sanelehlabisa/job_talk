# Run through local-signoff.ps1 -DraftEditorOnly. Creates one fictional draft;
# never changes the recruiter's other conversations or publishes this fixture.
Invoke-JavaScript "document.querySelector('.new-chat').click(); true" | Out-Null
Wait-JavaScript "document.querySelectorAll('.template-choice').length === 3" 'template picker'
Invoke-JavaScript "document.querySelector('[data-template-id=generic-role]').click(); true" | Out-Null
Wait-JavaScript "document.querySelector('.draft-sidebar [data-field-state=unanswered]') !== null" 'blank draft'
Set-InputAndSubmit "textarea[aria-label='Conversation message']" 'Job title: Draft Editor Check Engineer; Role description: Design and test PCB circuits; Work arrangement: on-site; Location: Durban; Skills: circuit design is required; No experience required; No degree needed.'
Wait-JavaScript "document.querySelector('[data-field-key=job_title]')?.textContent.includes('Draft Editor Check Engineer') && !document.querySelector('.typing')" 'captured role' 45
Invoke-JavaScript "[...document.querySelectorAll('.template-draft button')].find(b => b.textContent === 'Add a field').click(); true" | Out-Null
Wait-JavaScript "document.querySelector('.draft-field-form') !== null" 'add field form'
Invoke-JavaScript @'
(() => {
  const set = (name, value) => {
    const input = document.querySelector('.draft-field-form [name=' + name + ']');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', {bubbles:true}));
  };
  set('label', 'PCB soldering');
  set('target', 'Must solder pcb compnents safly');
  document.querySelector('.draft-field-form').requestSubmit();
  return true;
})()
'@ | Out-Null
Wait-JavaScript "document.querySelector('[data-field-key=pcb_soldering]')?.dataset.fieldState === 'confirmed' && !document.querySelector('.draft-field-form')" 'saved added field' 45
if (-not (Invoke-JavaScript "document.querySelector('.template-draft [role=status]')?.textContent.includes('polished')")) { throw 'AI form polishing did not succeed' }
if (Invoke-JavaScript "document.querySelector('[data-field-key=pcb_soldering]').textContent.includes('compnents')") { throw 'Misspelled form wording was not polished' }
Invoke-JavaScript 'document.querySelector("[aria-label=''Edit PCB soldering'']").click(); true' | Out-Null
Wait-JavaScript "document.querySelector('.draft-field-form') !== null" 'edit existing field'
if (-not (Invoke-JavaScript 'document.querySelector("[aria-label=''Conversation message'']").disabled')) { throw 'Chat can overwrite an unsaved form edit' }
Set-InputAndSubmit '.draft-field-form [name=target]' 'Must solder and inspect PCB joints safely'
Wait-JavaScript "document.querySelector('[data-field-key=pcb_soldering]')?.textContent.toLowerCase().includes('inspect') && !document.querySelector('.draft-field-form')" 'edited requirement' 45
Invoke-JavaScript "document.querySelector('[data-field-key=tools] button[aria-label^=Remove]').click(); true" | Out-Null
Wait-JavaScript "!document.querySelector('[data-field-key=tools]') && !document.querySelector('.typing')" 'removed tools suggestion'
Invoke-JavaScript "[...document.querySelectorAll('.template-draft > button')].find(b => b.textContent === 'Done').click(); true" | Out-Null
Wait-JavaScript "document.querySelector('.publish-bar') !== null && !document.querySelector('.typing')" 'Done and final publish action'
if (Invoke-JavaScript "document.querySelector('.draft-sidebar [data-field-state=unanswered]') !== null") { throw 'Done retained a blank optional field' }
Save-Screenshot 'draft-editor-desktop.png'
Invoke-JavaScript 'window.__draftEditorReload = true; true' | Out-Null
Invoke-Cdp 'Page.reload' | Out-Null
Wait-JavaScript "!window.__draftEditorReload && document.querySelector('[data-field-key=pcb_soldering]')?.textContent.toLowerCase().includes('inspect')" 'saved edit after refresh'
Set-Viewport 390 760 $true
Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" 'closed phone menu'
Invoke-JavaScript "document.querySelector('.template-draft').scrollIntoView({block:'start',behavior:'instant'}); true" | Out-Null
Save-Screenshot 'draft-editor-phone.png'
Invoke-JavaScript 'document.querySelector("[aria-label=''Edit PCB soldering'']").click(); true' | Out-Null
Wait-JavaScript "document.querySelector('.draft-field-form') !== null" 'phone edit form'
Invoke-JavaScript "document.querySelector('.draft-field-form').scrollIntoView({block:'center',behavior:'instant'}); true" | Out-Null
Save-Screenshot 'draft-editor-form-phone.png'
if (Invoke-JavaScript "document.documentElement.scrollWidth > innerWidth || document.querySelector('.error-notice, .draft-error') !== null") { throw 'Draft editor error or phone overflow' }
Write-Output 'Draft editor browser check passed: actual Gemini capture, add and polish, edit, remove, Done, explicit Publish remains, reload persistence and phone layout. Fictional draft left unpublished.'
Write-Output "Screenshots: $OutputDirectory"
