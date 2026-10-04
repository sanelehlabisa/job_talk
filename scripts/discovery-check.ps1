# Uses current public vacancies read-only and deletes only its new test guest.
$discoverySession = $null
function Assert-DiscoveryCards {
    return Invoke-JavaScript @'
(async () => {
  const token=JSON.parse(sessionStorage.getItem('job-talk-session')).access_token;
  const chatId=document.querySelector('.chat-row.active').dataset.chatId;
  const response=await fetch('http://localhost:8000/api/chats/'+chatId+'/recommendations',{headers:{Authorization:'Bearer '+token}});
  const items=await response.json();
  const cards=[...document.querySelectorAll('.discovery-sidebar .job-card')];
  const reply=[...document.querySelectorAll('.message-wrap.assistant .message p')].at(-1)?.textContent;
  if (cards.length!==items.length || cards.length>2) throw new Error('Card count differs from backend');
  cards.forEach((card,index)=>{
    if (card.querySelector('h3').textContent!==items[index].job.title || card.querySelector('.job-logo').textContent!==String(index+1)) throw new Error('Job order/number mismatch');
    if (!reply.includes((index+1)+'. '+items[index].job.title)) throw new Error('Chat reply does not name the visible job');
  });
  if (document.querySelector('.discovery-empty, .profile-chips, .discovery-sidebar .score, .discovery-sidebar .criteria-row')) throw new Error('Discovery intro/chips/percentages remain');
  if (reply.includes('as they become available') || reply.includes('Where are you based')) throw new Error('Generic or repeated discovery reply');
  return items.map(item=>({id:item.job.id,title:item.job.title,score:item.match_score,example:item.available_example}));
})()
'@
}

try {
    Invoke-JavaScript "[...document.querySelectorAll('.entry-choice')].find(b=>b.textContent.includes('looking for work')).click(); true" | Out-Null
    Wait-JavaScript "[...document.querySelectorAll('button')].some(b=>b.textContent.includes('Find a different job'))" 'seeker entry'
    Invoke-JavaScript "[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Find a different job')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.discovery-empty') !== null && document.querySelectorAll('.discovery-sidebar .job-card').length > 0" 'initial guidance and examples'
    $discoverySession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"
    Save-Screenshot 'discovery-initial.png'
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" 'I am looking for a software engineer job. I am currenlty in Cape Town but willing to relocate to anywhere within the country. I have 3 years experience in full stack plus machine learning and even hardware'
    Wait-JavaScript "!document.querySelector('.typing') && document.querySelectorAll('.message-wrap.user').length === 1 && document.querySelectorAll('.message-wrap.assistant').length === 2" 'first real discovery reply' 45
    $first = Assert-DiscoveryCards
    Save-Screenshot 'discovery-first-reply.png'
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" 'are there any available jobs for those skill that i have, full stack that inlcudes JavaScript, Type Script, FastAPI and PostGRESQL'
    Wait-JavaScript "!document.querySelector('.typing') && document.querySelectorAll('.message-wrap.user').length === 2 && document.querySelectorAll('.message-wrap.assistant').length === 3" 'second real discovery reply' 45
    $second = Assert-DiscoveryCards
    if (-not ($second | Where-Object { -not $_.example })) { throw 'Software background did not find a possible role among current public jobs' }
    if (Invoke-JavaScript "document.querySelector('.error-notice') !== null") { throw 'Discovery displayed an error' }
    Save-Screenshot 'discovery-grounded-desktop.png'
    Set-Viewport 390 760 $true
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" 'closed phone conversation menu'
    Invoke-JavaScript "document.querySelector('.discovery-sidebar').scrollIntoView({block:'start',behavior:'instant'}); true" | Out-Null
    if (Invoke-JavaScript 'document.documentElement.scrollWidth > innerWidth') { throw 'Discovery overflows at phone width' }
    Save-Screenshot 'discovery-grounded-phone.png'
    Invoke-JavaScript 'window.__discoveryReload=true; true' | Out-Null
    Invoke-Cdp 'Page.reload' | Out-Null
    Wait-JavaScript "!window.__discoveryReload && document.querySelectorAll('.discovery-sidebar .job-card').length > 0 && document.querySelectorAll('.message-wrap.user').length === 2" 'restored discovery'
    Assert-DiscoveryCards | Out-Null
    # These are public titles and scores only, never guest tokens or contact data.
    Write-Output ('First turn: ' + ($first | ConvertTo-Json -Compress))
    Write-Output ('Second turn: ' + ($second | ConvertTo-Json -Compress))
    Write-Output 'Discovery browser check passed: actual conversation, numbered grounded replies/cards, no percentages, no repeated intro, phone layout and reload.'
} finally {
    if ($discoverySession) {
        $discoveryToken = (ConvertFrom-Json $discoverySession).access_token
        Invoke-RestMethod -Uri 'http://localhost:8000/api/account' -Method Delete -Headers @{Authorization="Bearer $discoveryToken"} | Out-Null
    }
}
