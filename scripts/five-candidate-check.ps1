# Use local-signoff.ps1 -FiveCandidates. UI performs every job/application write;
# authenticated reads check persisted results. Finally closes/deletes only fixtures.
$scenarioJob = $null
$scenarioPublished = $false
$scenarioSessions = @()
$recruiterSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"
$scenarioTitle = 'Browser Check Python Backend Developer ' + (Get-Date -Format 'HHmmss')
$scenarioReport = @()

function Get-ScenarioChat {
    Wait-JavaScript "document.querySelector('.chat-row.active') !== null" 'saved conversation in sidebar'
    Invoke-JavaScript @'
(async () => {
  const token=JSON.parse(sessionStorage.getItem('job-talk-session')).access_token;
  const id=document.querySelector('.chat-row.active').dataset.chatId;
  const response=await fetch('http://localhost:8000/api/chats/'+id,{headers:{Authorization:'Bearer '+token}});
  if(!response.ok) throw new Error('Could not inspect current chat');
  return response.json();
})()
'@
}

function Send-ScenarioMessage([string]$message) {
    $before = Invoke-JavaScript "document.querySelectorAll('.message-wrap.assistant').length"
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" $message
    Wait-JavaScript "document.querySelectorAll('.message-wrap.assistant').length > $before && !document.querySelector('.typing') && !document.querySelector('.error-notice')" 'saved chat response' 60
}

function Get-ScenarioRecommendations {
    Wait-JavaScript "document.querySelector('.chat-row.active') !== null" 'discovery sidebar'
    Invoke-JavaScript @'
(async () => {
  const token=JSON.parse(sessionStorage.getItem('job-talk-session')).access_token;
  const id=document.querySelector('.chat-row.active').dataset.chatId;
  const response=await fetch('http://localhost:8000/api/chats/'+id+'/recommendations',{headers:{Authorization:'Bearer '+token}});
  if(!response.ok) throw new Error('Could not inspect recommendations');
  return response.json();
})()
'@
}

try {
    Invoke-JavaScript "document.querySelector('.new-chat').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('[data-template-id=generic-role]') !== null" 'role starter'
    Invoke-JavaScript "document.querySelector('[data-template-id=generic-role]').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.composer') !== null" 'draft'
    $draft = Get-ScenarioChat
    $scenarioJob = $draft.job_post.id
    $scenarioChat = $draft.id
    Send-ScenarioMessage "The job title is $scenarioTitle. The person will build and test Python REST APIs for a booking service using FastAPI and PostgreSQL."
    Send-ScenarioMessage 'The job is in Cape Town, South Africa. Hybrid work is required, with two days per week at the office.'
    Send-ScenarioMessage 'Require three years of Python backend development experience. Python API development is a required skill. FastAPI and PostgreSQL are required tools.'
    Send-ScenarioMessage 'Correction: require two years of Python backend development experience, not three years. Working hours are 40 hours per week on weekdays. No degree or qualification is required. The start date is flexible.'
    Invoke-JavaScript "[...document.querySelectorAll('.template-draft button')].find(b=>b.textContent.trim()==='Done').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.publish-bar button') && !document.querySelector('.publish-bar button').disabled && !document.querySelector('.typing')" 'ready job summary' 60
    $draft = Get-ScenarioChat
    if (-not $draft.can_publish) { throw 'Job summary is not ready to publish' }
    $experienceField = $draft.job_draft.fields | Where-Object key -eq 'experience'
    if (($experienceField.target -as [string]) -notmatch '2|two') { throw 'Recruiter experience correction was not saved' }
    Save-Screenshot 'five-01-recruiter-review.png'
    Invoke-JavaScript "document.querySelector('.publish-bar button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.status-pill')?.textContent.includes('Published')" 'published role'
    $scenarioPublished = $true
    $published = Get-ScenarioChat
    $scenarioTitle = $published.job_post.title
    $criterionKeys = @($published.job_post.target_profile.PSObject.Properties.Name | Sort-Object)
    if ($criterionKeys -contains 'education') { throw 'No-degree requirement still affects scoring' }
    Write-Output 'PASS: recruiter email login, step-by-step chat, correction, review and publication'

    $people = @(
        @{name='Fictional Alex'; kind='strong'; location='Cape Town'; description='I am a Python backend developer in Cape Town with four years building and testing REST APIs using FastAPI and PostgreSQL. I built a booking API with automated tests. I can work hybrid with two office days and 40 weekday hours, and can start immediately.'},
        @{name='Fictional Bongi'; kind='strong'; location='Cape Town'; description='I have three years of Python backend API development, including three years using FastAPI and PostgreSQL to build tested inventory APIs. I live in Cape Town and want hybrid work with two office days. I can work 40 hours per week on weekdays and start next month.'},
        @{name='Fictional Casey'; kind='partial'; location='Cape Town'; description='I live in Cape Town and have one year of Python API experience from a small Flask project using SQLite. I do not have FastAPI or PostgreSQL skills. I can work hybrid with two office days, 40 weekday hours, and start immediately.'},
        @{name='Fictional Dumi'; kind='unrelated'; location='Cape Town'; description='I am a plumber in Cape Town with six years fixing leaking pipes, installing geysers and fitting taps with pipe cutters and wrenches. I want plumbing work, not software development. I have no Python, FastAPI, PostgreSQL or software API experience. I can work 40 weekday hours and start immediately.'},
        @{name='Fictional Erin'; kind='unrelated'; location='Durban'; description='I am a chef in Durban with eight years cooking meals and managing restaurant kitchens. I want on-site kitchen work in Durban, not software work. I have no Python, FastAPI, PostgreSQL or API development experience. I can work 40 weekday hours and start immediately.'}
    )
    foreach ($person in $people) {
        Invoke-JavaScript "sessionStorage.removeItem('job-talk-session'); location.href='/'; true" | Out-Null
        Wait-JavaScript "document.querySelector('.entry-choice') !== null" 'new guest entry'
        Invoke-JavaScript "[...document.querySelectorAll('.entry-choice')].find(b=>b.textContent.includes('looking for work')).click(); true" | Out-Null
        Wait-JavaScript "[...document.querySelectorAll('button')].some(b=>b.textContent.includes('Find a different job'))" 'job browsing'
        Invoke-JavaScript "[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Find a different job')).click(); true" | Out-Null
        Wait-JavaScript "document.querySelector('.composer') !== null" 'discovery chat'
        $guest = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"
        $scenarioSessions += $guest
        Send-ScenarioMessage $person.description
        $recommendations = @(Get-ScenarioRecommendations)
        $recommended = @($recommendations | Where-Object { $_.job.id -eq $scenarioJob -and -not $_.available_example }).Count -gt 0
        if ($person.kind -eq 'strong' -and -not $recommended) { throw "$($person.name): relevant new job missing from discovery" }
        if ($person.kind -eq 'unrelated' -and $recommended) { throw "$($person.name): unrelated work recommended as a match" }
        Save-Screenshot ('five-discovery-' + $person.name.Replace(' ', '-') + '.png')
        if ($recommended) {
            $titleJson = $scenarioTitle | ConvertTo-Json -Compress
            Invoke-JavaScript "[...document.querySelectorAll('.job-card')].find(c=>c.querySelector('h3')?.textContent === $titleJson).querySelector('button').click(); true" | Out-Null
        } else {
            # Deliberate application via public link; never count this as discovery.
            Invoke-JavaScript "sessionStorage.removeItem('job-talk-session'); location.href='/?job=$scenarioJob'; true" | Out-Null
            Wait-JavaScript "document.querySelector('.entry-job') !== null" 'direct public job'
            Invoke-JavaScript "document.querySelector('.entry-job').click(); true" | Out-Null
            Wait-JavaScript "document.querySelector('.composer') !== null" 'direct application'
            $scenarioSessions += (Invoke-JavaScript "sessionStorage.getItem('job-talk-session')")
        }
        Wait-JavaScript "document.querySelector('.application-summary') !== null && !document.querySelector('.typing')" 'matching application form' 60
        Send-ScenarioMessage $person.description
        $application = Get-ScenarioChat
        $fieldKeys = @($application.application_fields | ForEach-Object key | Sort-Object)
        if (($criterionKeys -join ',') -ne ($fieldKeys -join ',')) { throw 'Application form differs from published criteria' }
        $unanswered = @($application.application_fields | Where-Object { $_.state -in @('unanswered','unclear') })
        if ($unanswered.Count -and $person.kind -eq 'unrelated') {
            # Answer the job's focused follow-up rather than assuming generic
            # trade/kitchen experience answers a software-experience question.
            Send-ScenarioMessage 'I have zero years of Python backend development experience and cannot develop Python APIs. I have never used FastAPI or PostgreSQL. I only want on-site work, not hybrid office work.'
            $application = Get-ScenarioChat
            $unanswered = @($application.application_fields | Where-Object { $_.state -in @('unanswered','unclear') })
        }
        if ($unanswered.Count) { throw "$($person.name): fields still unanswered: $($unanswered.key -join ', ')" }
        $nameJson = $person.name | ConvertTo-Json -Compress
        $locationJson = $person.location | ConvertTo-Json -Compress
        $contactJson = ($person.name.ToLower().Replace(' ', '-') + '@example.test') | ConvertTo-Json -Compress
        Invoke-JavaScript @"
(async () => {
  for(const [selector,value] of [['#candidate-name',$nameJson],['#candidate-location',$locationJson],['#candidate-contact',$contactJson]]) {
    const input=document.querySelector(selector);
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,value);
    input.dispatchEvent(new Event('input',{bubbles:true}));
    await new Promise(resolve=>setTimeout(resolve,0));
  }
  document.querySelector('.consent-check input').click();
  document.querySelector('.application-review').requestSubmit();
  return true;
})()
"@ | Out-Null
        Wait-JavaScript "document.querySelector('.submitted-bar')?.textContent.includes('Application submitted')" 'submitted reviewed application' 60
        Wait-JavaScript "/^\d+%$/.test(document.querySelector('.application-match strong')?.textContent)" 'loaded submitted score' 30
        $result = Invoke-JavaScript @'
(async () => {
  const token=JSON.parse(sessionStorage.getItem('job-talk-session')).access_token;
  const items=await fetch('http://localhost:8000/api/applications',{headers:{Authorization:'Bearer '+token}}).then(r=>r.json());
  return items[0];
})()
'@
        $score = [Math]::Floor($result.match_result.overall_score * 100 + 0.5)
        $visibleScore = Invoke-JavaScript "document.querySelector('.application-match strong').textContent"
        if ($visibleScore -ne "$score%") { throw "Visible applicant score $visibleScore differs from submitted $score%" }
        $scenarioReport += @{name=$person.name;kind=$person.kind;discovered=$recommended;score=$score;source=$result.match_result.rating_source;id=$result.id}
        $scenarioReport | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $OutputDirectory 'five-candidate-results.json')
        Write-Output "PASS: $($person.name) ($($person.kind)), discovery=$recommended, submitted=$score%, source=$($result.match_result.rating_source)"
    }

    $recruiterJson = $recruiterSession | ConvertTo-Json -Compress
    Invoke-JavaScript "sessionStorage.setItem('job-talk-session',$recruiterJson); location.href='/'; true" | Out-Null
    Wait-JavaScript "document.querySelector('[data-chat-id=`"$scenarioChat`"]') !== null" 'recruiter workspace'
    Invoke-JavaScript "document.querySelector('[data-chat-id=`"$scenarioChat`"]')?.click(); true" | Out-Null
    Wait-JavaScript "document.querySelectorAll('.candidate-card').length === 5" 'five submitted candidates'
    $ranked = Invoke-JavaScript "[...document.querySelectorAll('.candidate-card')].map(c=>({name:c.querySelector('h3').textContent,score:c.querySelector('.score strong').textContent,contact:c.querySelector('a').textContent,criteria:c.querySelectorAll('.criterion-item').length}))"
    $strongNames = @($scenarioReport | Where-Object kind -eq 'strong' | ForEach-Object name)
    foreach ($card in $ranked | Select-Object -First 2) {
        if ($card.name -notin $strongNames) { throw 'Strong relevant applicants are not the top two' }
    }
    foreach ($card in $ranked) {
        $expected = $scenarioReport | Where-Object name -eq $card.name
        if ($card.score -ne "$($expected.score)%" -or $card.criteria -ne $criterionKeys.Count -or $card.contact -notlike '*@example.test') { throw 'Recruiter card differs from reviewed application' }
    }
    if (-not (Invoke-JavaScript "document.querySelector('.parallel-plot') !== null && document.querySelectorAll('.plot-candidate').length === 5")) { throw 'Comparison plot missing candidates' }
    Invoke-JavaScript @"
(async () => {
  const token=JSON.parse(sessionStorage.getItem('job-talk-session')).access_token;
  const items=await fetch('http://localhost:8000/api/applications?job_id=$scenarioJob',{headers:{Authorization:'Bearer '+token}}).then(r=>r.json());
  const chat=await fetch('http://localhost:8000/api/chats/$scenarioChat',{headers:{Authorization:'Bearer '+token}}).then(r=>r.json());
  const keys=Object.keys(chat.job_post.target_profile).sort();
  for(const app of items) {
    if(Object.keys(app.match_result.criteria).sort().join(',')!==keys.join(',')) throw new Error('Saved assessment criteria differ');
    const name=app.candidate_profile.candidate_details.name;
    const plot=[...document.querySelectorAll('.plot-candidate')].find(p=>p.getAttribute('aria-label')===name+' score line');
    const titles=[...plot.querySelectorAll('title')].map(t=>t.textContent);
    for(const [key,value] of Object.entries(app.match_result.criteria).slice(0,8)) {
      const expected=value.gap==='missing' || !value.evidence ? name+': no direct evidence for '+key.replaceAll('_',' ') : name+': '+key.replaceAll('_',' ')+' '+Math.round(value.score*100)+'%';
      if(!titles.includes(expected)) throw new Error('Plot differs from saved criterion score');
    }
  }
  return true;
})()
"@ | Out-Null
    Save-Screenshot 'five-02-recruiter-comparison.png'
    Invoke-Cdp 'Page.reload' | Out-Null
    Wait-JavaScript "document.querySelectorAll('.candidate-card').length === 5" 'saved comparison after refresh'
    Set-Viewport 390 760 $true
    Save-Screenshot 'five-03-recruiter-phone.png'
    $scenarioReport | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $OutputDirectory 'five-candidate-results.json')
    Write-Output 'PASS: five saved applications, relevant top two, contact/evidence, shared criteria, comparison plot and refresh'
} catch {
    Save-Screenshot 'five-failure.png'
    throw
} finally {
    foreach ($session in $scenarioSessions) {
        $token = (ConvertFrom-Json $session).access_token
        Invoke-RestMethod -Uri 'http://localhost:8000/api/account' -Method Delete -Headers @{Authorization="Bearer $token"} | Out-Null
    }
    if ($scenarioJob -and $scenarioPublished) {
        $token = (ConvertFrom-Json $recruiterSession).access_token
        Invoke-RestMethod -Uri "http://localhost:8000/api/jobs/$scenarioJob/close" -Method Post -Headers @{Authorization="Bearer $token"} | Out-Null
    }
}
