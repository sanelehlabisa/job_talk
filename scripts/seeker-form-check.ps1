# Run through local-signoff.ps1 -SeekerFormOnly with an approved test recruiter.
# Only creates a fictional job and guest; closes/deletes its own fixtures in finally.
$formJobId = $null
$formGuestSession = $null
$formRecruiterSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"

function Assert-MatchScore {
    return Invoke-JavaScript @'
(async () => {
  const token=JSON.parse(sessionStorage.getItem('job-talk-session')).access_token;
  const chatId=Number(document.querySelector('.chat-row.active').dataset.chatId);
  const submitted=document.querySelector('.application-match')?.textContent.includes('Submitted match');
  const items=await fetch('http://localhost:8000/api/'+(submitted ? 'applications' : 'chats/'+chatId+'/recommendations'),{headers:{Authorization:'Bearer '+token}}).then(r=>r.json());
  const score=submitted ? items.find(item=>item.candidate_chat_id===chatId)?.match_result.overall_score : items[0]?.match_score;
  const source=submitted ? items.find(item=>item.candidate_chat_id===chatId)?.match_result.rating_source : items[0]?.rating_source;
  if (!Number.isFinite(score) || document.querySelector('.application-match strong')?.textContent !== Math.round(score*100)+'%') throw new Error('Visible match score differs from saved backend score');
  const label=source==='gemini' ? 'AI estimate' : 'Rule-based estimate';
  if (!document.querySelector('.application-match small')?.textContent.includes(label)) throw new Error('Estimate source label differs from backend');
  return score;
})()
'@
}

function Save-Answer([string]$key, [string]$value) {
    $keyJson = $key | ConvertTo-Json -Compress
    $valueJson = $value | ConvertTo-Json -Compress
    Invoke-JavaScript @"
(async () => {
  const input = document.querySelector('#answer-' + $keyJson);
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, $valueJson);
  input.dispatchEvent(new Event('input', {bubbles:true}));
  await new Promise(resolve => setTimeout(resolve, 0));
  if (!document.querySelector('[aria-label="Conversation message"]').disabled) throw new Error('Chat is not locked during editing');
  input.form.requestSubmit();
  return true;
})()
"@ | Out-Null
    Wait-JavaScript "document.querySelector('.application-summary [role=status]')?.textContent.includes('Answer saved') && !document.querySelector('.typing')" 'saved answer'
    Assert-MatchScore | Out-Null
}

try {
    Invoke-JavaScript @'
(async () => {
  const icon=document.querySelector('link[rel=icon]');
  const logo=document.querySelector('.brand-mark');
  if (!icon || !logo?.complete || !logo.naturalWidth || icon.href !== logo.src) throw new Error('Shared logo/favicon is missing');
  const response=await fetch(icon.href);
  if (!response.ok || !response.headers.get('content-type')?.includes('image/svg+xml')) throw new Error('SVG browser icon did not load');
  return true;
})()
'@ | Out-Null
    Invoke-JavaScript "document.querySelector('.new-chat').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('[data-template-id=generic-role]') !== null" 'template picker'
    Invoke-JavaScript "document.querySelector('[data-template-id=generic-role]').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.composer') !== null" 'new fictional job'
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" 'Company name: Example Software; Company location: Cape Town; Job title: Seeker Form Check Developer. Role description: Build and test Python APIs. Work arrangement: on-site. Location: Cape Town. Skills: Python API development is required. Experience: two years of Python backend experience required. Working hours: 40 hours a week. No degree needed. No specific tools required. Start immediately.'
    Wait-JavaScript "document.querySelector('.publish-bar button') !== null && !document.querySelector('.typing')" 'publishable fictional role' 45
    $formJobId = Invoke-JavaScript @'
(async () => {
  const session=JSON.parse(sessionStorage.getItem('job-talk-session'));
  const ownId=document.querySelector('.chat-row.active')?.dataset.chatId;
  if (!ownId) throw new Error('Own fictional draft not found');
  const chat=await fetch('http://localhost:8000/api/chats/'+ownId,{headers:{Authorization:'Bearer '+session.access_token}}).then(r=>r.json());
  return chat.job_post.id;
})()
'@
    Invoke-JavaScript "document.querySelector('.publish-bar button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.status-pill')?.textContent.includes('Published')" 'published fixture'
    Invoke-JavaScript "sessionStorage.removeItem('job-talk-session'); location.href='/?job=$formJobId'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.entry-job') !== null" 'public job'
    Invoke-JavaScript "document.querySelector('.entry-job').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#answer-working_hours') !== null" 'application form'
    $formGuestSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"
    Wait-JavaScript "/^\d+%$/.test(document.querySelector('.application-match strong')?.textContent)" 'initial match score'
    $initialMatch = Assert-MatchScore
    if (Invoke-JavaScript "document.querySelector('.messages .job-card, .messages .application-review, .application-summary .draft-state') !== null || document.querySelector('[data-field-key=working_hours] p') !== null") { throw 'Duplicate application details remain' }
    if (-not (Invoke-JavaScript "document.querySelector('.application-summary button.primary.full')?.disabled")) { throw 'Submit should require consent' }
    Save-Answer 'experience' '1.5 years building Python APIs'
    if ((Assert-MatchScore) -le $initialMatch) { throw 'Saved experience did not improve the initial match score' }
    Save-Answer 'working_hours' '40 hours a week'
    if (Invoke-JavaScript "document.querySelectorAll('.message-wrap.user').length !== 0") { throw 'Form changes cluttered chat' }
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" 'I am based in Cape Town. Correction: I can work 30 hours a week.'
    Wait-JavaScript "document.querySelector('#answer-working_hours')?.value.includes('30') && !document.querySelector('.typing')" 'chat correction in form' 45
    $beforeGap = Assert-MatchScore
    if (-not (Invoke-JavaScript "document.querySelector('#answer-experience')?.value === '1.5 years building Python APIs'")) { throw 'Chat changed unrelated form answer' }
    Save-Answer 'experience' "I don't have that experience"
    if ((Assert-MatchScore) -ge $beforeGap) { throw 'Reported gap did not reduce the match score' }
    if (-not (Invoke-JavaScript "document.querySelector('[data-field-key=experience]')?.dataset.fieldState === 'gap'")) { throw 'Honest gap was not recorded' }
    Invoke-JavaScript "[...document.querySelectorAll('.application-summary button')].find(b=>b.getAttribute('aria-label') === 'Clear Working hours answer').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#answer-working_hours')?.value === '' && !document.querySelector('.typing')" 'cleared answer'
    Assert-MatchScore | Out-Null
    Save-Answer 'working_hours' '30 hours a week'
    Save-Screenshot 'seeker-form-desktop.png'
    Invoke-JavaScript "window.__formReload=true; true" | Out-Null
    Invoke-Cdp 'Page.reload' | Out-Null
    Wait-JavaScript "!window.__formReload && document.querySelector('#answer-working_hours')?.value === '30 hours a week'" 'saved answers after reload'
    Wait-JavaScript "/^\d+%$/.test(document.querySelector('.application-match strong')?.textContent)" 'reloaded match score'
    Assert-MatchScore | Out-Null
    Set-Viewport 390 760 $true
    Invoke-JavaScript "document.querySelector('.application-summary').scrollIntoView({block:'start',behavior:'instant'}); true" | Out-Null
    Save-Screenshot 'seeker-form-phone.png'
    if (Invoke-JavaScript 'document.documentElement.scrollWidth > innerWidth') { throw 'Phone form overflows horizontally' }
    Invoke-JavaScript @'
(async () => {
  for (const [selector,value] of [['#candidate-name','Seeker Form Candidate'],['#candidate-location','Cape Town'],['#candidate-contact','seeker-form@example.test']]) {
    const input=document.querySelector(selector);
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,value);
    input.dispatchEvent(new Event('input',{bubbles:true}));
    await new Promise(resolve=>setTimeout(resolve,0));
  }
  document.querySelector('.application-review .consent-check input').click();
  await new Promise(resolve=>setTimeout(resolve,0));
  document.querySelector('.application-review').scrollIntoView({block:'end',behavior:'instant'});
  return true;
})()
'@ | Out-Null
    Save-Screenshot 'seeker-form-submit-phone.png'
    Invoke-JavaScript "document.querySelector('.application-review').requestSubmit(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar')?.textContent.includes('Application submitted')" 'submitted from sidebar'
    Wait-JavaScript "/^\d+%$/.test(document.querySelector('.application-match strong')?.textContent)" 'submitted match score'
    Assert-MatchScore | Out-Null
    if (Invoke-JavaScript "document.querySelector('.application-review') !== null || !document.querySelector('#answer-working_hours').readOnly") { throw 'Submitted form remains editable' }
    Write-Output 'Seeker form browser check passed: shared logo/favicon, backend match score after edits/chat/gap/clear/reload/submission, phone layout and consent/submit.'
    Write-Output "Screenshots: $OutputDirectory"
} finally {
    if ($formGuestSession) {
        $formGuestToken = (ConvertFrom-Json $formGuestSession).access_token
        Invoke-RestMethod -Uri 'http://localhost:8000/api/account' -Method Delete -Headers @{Authorization="Bearer $formGuestToken"} | Out-Null
    }
    if ($formJobId) {
        $formRecruiterToken = (ConvertFrom-Json $formRecruiterSession).access_token
        Invoke-RestMethod -Uri "http://localhost:8000/api/jobs/$formJobId/close" -Method Post -Headers @{Authorization="Bearer $formRecruiterToken"} | Out-Null
    }
}
