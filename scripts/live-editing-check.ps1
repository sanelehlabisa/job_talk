# Run through local-signoff.ps1 -LiveEditingOnly with an approved test recruiter.
# Creates one fictional job and closes only that job, even if a check fails.
$editingJobId = $null
$editingRecruiterSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"
try {
    Invoke-JavaScript "document.querySelector('.new-chat').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('[data-template-id=generic-role]') !== null" 'template picker'
    Invoke-JavaScript "document.querySelector('[data-template-id=generic-role]').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.composer') !== null" 'new chat'
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" 'Company name: Example Circuits; Company location: Durban; Job title: Live Editing Check Technician. Role description: Design and test PCB circuits. Work arrangement: on-site. Location: Durban. Skills: circuit design is required. No experience required. No degree needed.'
    Wait-JavaScript "document.querySelector('[data-field-key=job_title] input[name=value]')?.value.includes('Live Editing Check Technician') && !document.querySelector('.typing')" 'captured role' 45
    Invoke-JavaScript "[...document.querySelectorAll('.template-draft > button')].find(b => b.textContent === 'Done').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.publish-bar button') !== null && !document.querySelector('.typing')" 'publish readiness'
    $editingJobId = Invoke-JavaScript @'
(async () => {
  const session = JSON.parse(sessionStorage.getItem('job-talk-session'));
  const chats = await fetch('http://localhost:8000/api/chats', {headers:{Authorization:'Bearer '+session.access_token}}).then(r=>r.json());
  const created=chats.find(c=>c.workspace_title==='Live Editing Check Technician');
  if (!created) return null;
  const chat=await fetch('http://localhost:8000/api/chats/'+created.id,{headers:{Authorization:'Bearer '+session.access_token}}).then(r=>r.json());
  return chat.job_post.id;
})()
'@
    if (-not $editingJobId) { throw 'Own test job was not found' }
    Invoke-JavaScript "document.querySelector('.publish-bar button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.status-pill')?.textContent.includes('Published') && document.querySelector('.composer') !== null" 'published editable chat'
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" 'Change the job title to Live Editing Check Engineer'
    Wait-JavaScript "document.querySelector('[data-field-key=job_title] input[name=value]')?.value.includes('Live Editing Check Engineer') && !document.querySelector('.typing')" 'published chat correction' 45
    if (-not (Invoke-JavaScript "fetch('http://localhost:8000/api/public/jobs/$editingJobId').then(r=>r.json()).then(j=>j.title==='Live Editing Check Technician')")) { throw 'Unpublished edit changed the live post' }
    Wait-JavaScript "document.querySelector('.publish-bar button')?.textContent.includes('Publish changes')" 'explicit Publish changes'
    Invoke-JavaScript "document.querySelector('.publish-bar button').click(); true" | Out-Null
    Wait-JavaScript "!document.querySelector('.publish-bar') && document.querySelector('.composer') !== null" 'republished editable chat'
    if (-not (Invoke-JavaScript "fetch('http://localhost:8000/api/public/jobs/$editingJobId').then(r=>r.json()).then(j=>j.title==='Live Editing Check Engineer')")) { throw 'Public post did not update' }
    Save-Screenshot 'live-editing-desktop.png'
    Invoke-JavaScript 'window.__editingReload = true; true' | Out-Null
    Invoke-Cdp 'Page.reload' | Out-Null
    Wait-JavaScript "!window.__editingReload && document.querySelector('.composer') !== null && document.querySelector('[data-field-key=job_title] input[name=value]')?.value.includes('Live Editing Check Engineer')" 'editable published job after reload'

    # Start a fresh accountless discovery conversation; no existing candidate is changed.
    Invoke-JavaScript "sessionStorage.removeItem('job-talk-session'); location.href='/'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.entry-choice') !== null" 'entry screen'
    Invoke-JavaScript "[...document.querySelectorAll('.entry-choice')].find(b=>b.textContent.includes('looking for work')).click(); true" | Out-Null
    Wait-JavaScript "[...document.querySelectorAll('button')].some(b=>b.textContent.includes('Find a different job'))" 'discovery entry'
    Invoke-JavaScript "[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Find a different job')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.discovery-sidebar .job-card') !== null" 'immediate job examples'
    if (Invoke-JavaScript "document.querySelectorAll('.message-wrap.user').length !== 0 || document.querySelector('.discovery-sidebar .score') !== null") { throw 'Initial examples require input or claim a match score' }
    Save-Screenshot 'discovery-examples-desktop.png'
    Set-Viewport 390 760 $true
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" 'closed discovery phone menu'
    Invoke-JavaScript "document.querySelector('.discovery-sidebar').scrollIntoView({block:'start',behavior:'instant'}); true" | Out-Null
    Save-Screenshot 'discovery-examples-phone.png'
    if (Invoke-JavaScript 'document.documentElement.scrollWidth > innerWidth') { throw 'Phone discovery overflows horizontally' }
    Set-Viewport 1200 800 $false
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" 'I have three years of circuit design experience. I design and test PCB circuits, live in Durban and can work on-site.'
    Wait-JavaScript "!document.querySelector('.typing') && document.querySelectorAll('.message-wrap.user').length === 1 && document.querySelector('.discovery-heading')?.textContent === 'Possible roles'" 'context-based suggestions' 45
    if (Invoke-JavaScript "document.querySelector('.discovery-empty, .discovery-sidebar .score, .discovery-sidebar .criteria-row') !== null") { throw 'Discovery still displays introduction or percentages after matching' }
    Save-Screenshot 'discovery-matches-desktop.png'
    if (Invoke-JavaScript "document.querySelector('.error-notice, .draft-error') !== null") { throw 'UI displayed an error' }
    # Delete only the newly created test guest and its conversation.
    Invoke-JavaScript @'
(async () => {
  const session=JSON.parse(sessionStorage.getItem('job-talk-session'));
  const response=await fetch('http://localhost:8000/api/account',{method:'DELETE',headers:{Authorization:'Bearer '+session.access_token}});
  if (!response.ok) throw new Error('Test guest cleanup failed');
  return true;
})()
'@ | Out-Null
    Write-Output 'Browser check passed: published chat editing, explicit Publish changes, public update, reload, immediate available examples, context-based suggestions and phone layout.'
    Write-Output "Screenshots: $OutputDirectory"
} finally {
    if ($editingJobId) {
        $editingToken = (ConvertFrom-Json $editingRecruiterSession).access_token
        Invoke-RestMethod -Uri "http://localhost:8000/api/jobs/$editingJobId/close" -Method Post -Headers @{Authorization="Bearer $editingToken"} | Out-Null
    }
}
