# Run through local-signoff.ps1 -AdminOnly. Uses the real owner email-code session.
# Needs another recruiter's draft and open job; no LLM requests or job mutations.
Wait-JavaScript "document.querySelector('.chat-list-label')?.textContent.includes('ALL HIRING') && document.querySelector('.chat-shell') !== null" 'shared admin workspace'
if (Invoke-JavaScript "document.querySelector('#admin-job, .admin-nav') !== null") { throw 'Separate admin dashboard remains' }
$adminCheckToken = $null
try {
    $fixture = Invoke-JavaScript @'
(async () => {
  const base = 'http://localhost:8000/api';
  const session = JSON.parse(sessionStorage.getItem('job-talk-session'));
  const headers = {Authorization: 'Bearer ' + session.access_token};
  const chats = await fetch(base + '/chats', {headers}).then(r => r.json());
  const others = chats.filter(c => c.recruiter_email !== session.user.email);
  const draft = others.find(c => c.status === 'draft');
  const open = others.find(c => c.status === 'published');
  if (!draft || !open) throw new Error('Need another recruiter\'s draft and published job');
  const detail = await fetch(base + '/chats/' + open.id, {headers}).then(r => r.json());
  const jobId = detail.job_post.id;
  const guest = await fetch(base + '/auth/guest', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({job_id:jobId})}).then(r => r.json());
  window.__adminCheckGuest = guest.access_token;
  const guestHeaders = {Authorization:'Bearer ' + guest.access_token, 'Content-Type':'application/json'};
  const guestChats = await fetch(base + '/chats', {headers:guestHeaders}).then(r => r.json());
  const applied = await fetch(base + '/jobs/' + jobId + '/apply', {method:'POST', headers:guestHeaders, body:JSON.stringify({candidate_chat_id:guestChats[0].id, candidate_name:'Owner View Check', candidate_location:'Cape Town', preferred_contact:'owner-check@example.test', consent_to_share:true})});
  if (!applied.ok) throw new Error('Fictional application failed');
  return {draftId:draft.id, openId:open.id};
})()
'@
    $adminCheckToken = Invoke-JavaScript 'window.__adminCheckGuest'
    Invoke-JavaScript "[...document.querySelectorAll('.chat-row')].find(b => b.dataset.chatId === '$($fixture.draftId)').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.template-draft') !== null && document.querySelector('.composer') !== null" 'editable other recruiter draft'
    Save-Screenshot 'admin-shared-draft-desktop.png'
    Invoke-JavaScript "[...document.querySelectorAll('.chat-row')].find(b => b.dataset.chatId === '$($fixture.openId)').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.candidate-comparison')?.textContent.includes('Owner View Check') && document.querySelector('.close-job') !== null" 'shared comparison and close control'
    Save-Screenshot 'admin-shared-comparison-desktop.png'
    Invoke-Cdp 'Page.reload' | Out-Null
    Wait-JavaScript "document.querySelector('.chat-list-label')?.textContent.includes('ALL HIRING') && document.querySelector('.chat-shell') !== null" 'shared workspace after refresh'
    Set-Viewport 390 760 $true
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" 'closed phone sidebar'
    Invoke-JavaScript 'document.querySelector("[aria-label=''Open conversation menu'']").click(); true' | Out-Null
    Wait-JavaScript "Math.abs(document.querySelector('.sidebar.open')?.getBoundingClientRect().left ?? -999) < 1" 'phone conversations'
    Save-Screenshot 'admin-shared-navigation-phone.png'
    Invoke-JavaScript "[...document.querySelectorAll('.chat-row')].find(b => b.dataset.chatId === '$($fixture.draftId)').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.sidebar.open') === null && document.querySelector('.composer') !== null" 'phone draft editing'
    if (Invoke-JavaScript "document.documentElement.scrollWidth > innerWidth || document.querySelector('.error-notice') !== null") { throw 'Shared workspace error or overflow' }
    Save-Screenshot 'admin-shared-draft-phone.png'
    Write-Output 'Admin browser check passed: shared chat list, owner labels, another recruiter draft with editing controls, comparison/close, refresh and phone navigation. No LLM calls made.'
    Write-Output "Screenshots: $OutputDirectory"
} finally {
    if (-not $adminCheckToken) { $adminCheckToken = Invoke-JavaScript 'window.__adminCheckGuest' }
    if ($adminCheckToken) {
        Invoke-RestMethod -Method Delete -Uri 'http://localhost:8000/api/account' -Headers @{Authorization = "Bearer $adminCheckToken"} | Out-Null
    }
}
