param(
    [string]$RecruiterEmail = "recruiter@example.com",
    [string]$OutputDirectory = "$env:TEMP/jobtalk-local-signoff"
)

$ErrorActionPreference = "Stop"
$edgePath = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
$debugPort = 9341
$profilePath = "$env:TEMP/jobtalk-local-signoff-profile-$PID"
$script:socket = $null
$script:messageId = 0

function Invoke-Cdp([string]$method, [hashtable]$params = @{}) {
    $script:messageId += 1
    $requestId = $script:messageId
    $payload = @{ id = $requestId; method = $method; params = $params } | ConvertTo-Json -Depth 20 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
    $segment = [ArraySegment[byte]]::new($bytes)
    $script:socket.SendAsync($segment, [Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).GetAwaiter().GetResult()

    while ($true) {
        $stream = [IO.MemoryStream]::new()
        do {
            $buffer = New-Object byte[] 65536
            $receiveSegment = [ArraySegment[byte]]::new($buffer)
            $received = $script:socket.ReceiveAsync($receiveSegment, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
            $stream.Write($buffer, 0, $received.Count)
        } while (-not $received.EndOfMessage)
        $response = [Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
        if ($response.id -eq $requestId) {
            if ($response.error) { throw "CDP $method failed: $($response.error.message)" }
            return $response.result
        }
    }
}

function Invoke-JavaScript([string]$expression) {
    $result = Invoke-Cdp "Runtime.evaluate" @{
        expression = $expression
        awaitPromise = $true
        returnByValue = $true
    }
    if ($result.exceptionDetails) {
        $detail = $result.exceptionDetails.exception.description
        if (-not $detail) { $detail = $result.exceptionDetails.text }
        throw "Browser JavaScript failed: $detail"
    }
    return $result.result.value
}

function Wait-JavaScript([string]$expression, [string]$description, [int]$seconds = 30) {
    $deadline = [DateTime]::UtcNow.AddSeconds($seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Invoke-JavaScript $expression) { return }
        Start-Sleep -Milliseconds 300
    }
    throw "Timed out waiting for $description"
}

function Save-Screenshot([string]$name) {
    $capture = Invoke-Cdp "Page.captureScreenshot" @{ format = "png"; fromSurface = $true }
    [IO.File]::WriteAllBytes((Join-Path $OutputDirectory $name), [Convert]::FromBase64String($capture.data))
}

function Set-Viewport([int]$width, [int]$height, [bool]$mobile) {
    Invoke-Cdp "Emulation.setDeviceMetricsOverride" @{
        width = $width
        height = $height
        deviceScaleFactor = 1
        mobile = $mobile
    } | Out-Null
}

function Set-InputAndSubmit([string]$selector, [string]$value) {
    $selectorJson = $selector | ConvertTo-Json -Compress
    $valueJson = $value | ConvertTo-Json -Compress
    $expression = @"
(() => {
  const input = document.querySelector($selectorJson);
  const prototype = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, 'value').set.call(input, $valueJson);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.form.requestSubmit();
  return true;
})()
"@
    Invoke-JavaScript $expression | Out-Null
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$edge = Start-Process -FilePath $edgePath -WindowStyle Hidden -PassThru -ArgumentList @(
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--remote-debugging-port=$debugPort",
    "--remote-allow-origins=*",
    "--user-data-dir=$profilePath",
    "about:blank"
)

try {
    $target = $null
    for ($attempt = 0; $attempt -lt 30 -and -not $target; $attempt++) {
        try {
            $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$debugPort/json" -TimeoutSec 2
            $target = $targets | Where-Object { $_.type -eq "page" } | Select-Object -First 1
        } catch {}
        if (-not $target) { Start-Sleep -Milliseconds 300 }
    }
    if (-not $target) { throw "Edge debugging endpoint did not start" }

    $script:socket = [Net.WebSockets.ClientWebSocket]::new()
    $script:socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, [Threading.CancellationToken]::None).GetAwaiter().GetResult() | Out-Null
    Invoke-Cdp "Page.enable" | Out-Null
    Invoke-Cdp "Runtime.enable" | Out-Null

    Set-Viewport 1200 800 $false
    Invoke-Cdp "Page.navigate" @{ url = "http://localhost:3000/" } | Out-Null
    Wait-JavaScript "document.querySelector('.entry-choice') !== null" "entry screen"
    Invoke-JavaScript "[...document.querySelectorAll('.entry-choice')].find(button => button.textContent.includes('hiring')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#email') !== null" "recruiter email form"
    $mailBefore = (Invoke-RestMethod -Uri "http://127.0.0.1:8025/api/v1/messages" -TimeoutSec 5).total
    Set-InputAndSubmit "#email" $RecruiterEmail
    Wait-JavaScript "document.querySelector('#code') !== null" "recruiter code form"

    $code = $null
    $mailDeadline = [DateTime]::UtcNow.AddSeconds(15)
    while ([DateTime]::UtcNow -lt $mailDeadline -and -not $code) {
        $mail = Invoke-RestMethod -Uri "http://127.0.0.1:8025/api/v1/messages" -TimeoutSec 5
        if ($mail.total -gt $mailBefore) {
            $message = $mail.messages |
                Where-Object { $_.Subject -eq "Your Job Talk sign-in code" -and $_.To[0].Address -eq $RecruiterEmail } |
                Sort-Object Created -Descending |
                Select-Object -First 1
            if ($message.Snippet -match "\b(\d{6})\b") { $code = $Matches[1] }
        }
        if (-not $code) { Start-Sleep -Milliseconds 300 }
    }
    if (-not $code) { throw "Recruiter sign-in code was not delivered" }
    Set-InputAndSubmit "#code" $code
    Wait-JavaScript "document.querySelector('.new-chat') !== null" "recruiter workspace"

    $chatCount = Invoke-JavaScript "document.querySelectorAll('.chat-row').length"
    Invoke-JavaScript "document.querySelector('.new-chat').click(); true" | Out-Null
    Wait-JavaScript "document.querySelectorAll('.chat-row').length > $chatCount && document.querySelectorAll('.message-wrap.user').length === 0" "new hiring conversation"
    $roleText = "Job title is Browser Signoff Welder. Welding is required with two years of experience. The role is based in Cape Town. The candidate should be available immediately."
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" $roleText
    Wait-JavaScript "document.querySelector('.publish-bar') !== null" "publish-ready role" 45
    if (Invoke-JavaScript "document.querySelector('.error-notice') !== null") { throw "Role creation displayed an error" }
    Save-Screenshot "01-role-ready-desktop.png"
    Set-Viewport 390 760 $true
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed recruiter phone sidebar" 10
    Save-Screenshot "02-role-ready-phone.png"
    Set-Viewport 1200 800 $false

    $jobId = Invoke-JavaScript @'
(async () => {
  const session = JSON.parse(sessionStorage.getItem('job-talk-session'));
  const headers = { Authorization: 'Bearer ' + session.access_token };
  const chats = await fetch('http://localhost:8000/api/chats', { headers }).then(response => response.json());
  const details = await Promise.all(chats.map(chat => fetch('http://localhost:8000/api/chats/' + chat.id, { headers }).then(response => response.json())));
  return details.find(chat => chat.job_post?.title === 'Browser Signoff Welder')?.job_post?.id || 0;
})()
'@
    if (-not $jobId) { throw "Created recruiter job was not found" }
    Invoke-JavaScript "document.querySelector('.publish-bar button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.status-pill').textContent.includes('Published')" "published role"
    $recruiterSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"

    Invoke-JavaScript "sessionStorage.removeItem('job-talk-session'); location.href='/?job=$jobId'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.entry-job')?.textContent.includes('Browser Signoff Welder')" "new public job"
    Save-Screenshot "03-public-job-desktop.png"
    Invoke-JavaScript "document.querySelector('.entry-job').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.chat-shell') !== null" "candidate conversation"
    $candidateText = "I have three years of welding experience in Cape Town. I repaired workshop gates and frames, and I am available immediately."
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" $candidateText
    Wait-JavaScript "document.querySelector('.profile-chips')?.textContent.includes('welding') && document.querySelector('.job-card .score strong')?.textContent !== '0%'" "captured candidate evidence" 45
    Invoke-JavaScript "document.querySelector('.job-card button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#candidate-name') !== null" "application review"
    $candidateForm = @"
(async () => {
  const setValue = async (selector, value) => {
    const input = document.querySelector(selector);
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(resolve => setTimeout(resolve, 0));
  };
  await setValue('#candidate-name', 'Local Signoff Candidate');
  if (document.querySelector('#candidate-location').value !== 'Cape Town') throw new Error('Candidate location was not extracted into review');
  await setValue('#candidate-contact', 'local-signoff@example.test');
  document.querySelector('.consent-check input').click();
  document.querySelector('.application-review').requestSubmit();
  return true;
})()
"@
    Invoke-JavaScript $candidateForm | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar') !== null" "submitted application"
    $candidateSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"
    Save-Screenshot "04-candidate-submitted-desktop.png"
    Set-Viewport 390 760 $true
    Invoke-Cdp "Page.reload" | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar') !== null" "candidate phone submission"
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed candidate phone sidebar" 10
    Save-Screenshot "05-candidate-submitted-phone.png"

    $recruiterSessionJson = $recruiterSession | ConvertTo-Json -Compress
    Set-Viewport 1200 800 $false
    Invoke-JavaScript "sessionStorage.setItem('job-talk-session', $recruiterSessionJson); location.href='/'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.chat-shell') !== null" "restored recruiter workspace"
    $jobChatIndex = Invoke-JavaScript @"
(async () => {
  const session = JSON.parse(sessionStorage.getItem('job-talk-session'));
  const headers = { Authorization: 'Bearer ' + session.access_token };
  const chats = await fetch('http://localhost:8000/api/chats', { headers }).then(response => response.json());
  const details = await Promise.all(chats.map(chat => fetch('http://localhost:8000/api/chats/' + chat.id, { headers }).then(response => response.json())));
  return details.findIndex(chat => chat.job_post?.id === $jobId);
})()
"@
    if ($jobChatIndex -lt 0) { throw "Created recruiter chat was not found" }
    Invoke-JavaScript "document.querySelectorAll('.chat-row')[$jobChatIndex].click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.candidate-card') !== null" "candidate comparison"
    Save-Screenshot "06-recruiter-comparison-desktop.png"
    Set-Viewport 390 760 $true
    Wait-JavaScript "document.querySelector('.candidate-card') !== null" "phone candidate comparison"
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed recruiter phone sidebar" 10
    Save-Screenshot "07-recruiter-comparison-phone.png"
    Invoke-JavaScript "window.confirm = () => true; document.querySelector('.close-job').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar')?.textContent.includes('Recruitment closed')" "closed recruitment"
    if (Invoke-JavaScript "document.querySelector('.publish-bar') !== null") { throw "Closed recruitment still offers publication" }
    Save-Screenshot "08-recruitment-closed-phone.png"
    $closedStatus = Invoke-JavaScript "fetch('http://localhost:8000/api/public/jobs/$jobId').then(response => response.status)"
    if ($closedStatus -ne 404) { throw "Closed job is still publicly available" }

    $candidateSessionJson = $candidateSession | ConvertTo-Json -Compress
    Invoke-JavaScript "sessionStorage.setItem('job-talk-session', $candidateSessionJson); location.href='/'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar') !== null" "restored candidate submission"
    Invoke-JavaScript "window.confirm = () => true; [...document.querySelectorAll('.submitted-bar button')].find(button => button.textContent.includes('Delete')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.entry-choice') !== null" "candidate data deletion"
    Save-Screenshot "09-candidate-deleted-phone.png"
    $candidateToken = (ConvertFrom-Json $candidateSession).access_token
    $candidateTokenJson = $candidateToken | ConvertTo-Json -Compress
    $deletedStatus = Invoke-JavaScript "fetch('http://localhost:8000/api/auth/me', { headers: { Authorization: 'Bearer ' + $candidateTokenJson } }).then(response => response.status)"
    if ($deletedStatus -ne 401) { throw "Deleted candidate session is still valid" }

    Write-Output "Local sign-off passed: create, publish, apply, compare, close, and delete on desktop and phone."
    Write-Output "Screenshots: $OutputDirectory"
} finally {
    if ($script:socket) { $script:socket.Dispose() }
    if ($edge -and -not $edge.HasExited) { Stop-Process -Id $edge.Id -Force }
}
