param(
    [int]$JobId = 2,
    [string]$RecruiterEmail = "recruiter@example.com",
    [string]$OutputDirectory = "$env:TEMP/jobtalk-browser-smoke"
)

$ErrorActionPreference = "Stop"
$edgePath = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
$debugPort = 9339
$profilePath = "$env:TEMP/jobtalk-browser-smoke-profile-$PID"
$script:socket = $null
$script:messageId = 0

function Invoke-Cdp([string]$method, [hashtable]$params = @{}) {
    $script:messageId += 1
    $requestId = $script:messageId
    $payload = @{ id = $requestId; method = $method; params = $params } | ConvertTo-Json -Depth 20 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
    $segment = [ArraySegment[byte]]::new($bytes)
    $script:socket.SendAsync(
        $segment,
        [Net.WebSockets.WebSocketMessageType]::Text,
        $true,
        [Threading.CancellationToken]::None
    ).GetAwaiter().GetResult()

    while ($true) {
        $stream = [IO.MemoryStream]::new()
        do {
            $buffer = New-Object byte[] 65536
            $receiveSegment = [ArraySegment[byte]]::new($buffer)
            $received = $script:socket.ReceiveAsync(
                $receiveSegment,
                [Threading.CancellationToken]::None
            ).GetAwaiter().GetResult()
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
    if ($result.exceptionDetails) { throw "Browser JavaScript failed" }
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
    [IO.File]::WriteAllBytes(
        (Join-Path $OutputDirectory $name),
        [Convert]::FromBase64String($capture.data)
    )
}

function Set-Viewport([int]$width, [int]$height, [bool]$mobile) {
    Invoke-Cdp "Emulation.setDeviceMetricsOverride" @{
        width = $width
        height = $height
        deviceScaleFactor = 1
        mobile = $mobile
    } | Out-Null
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
    $script:socket.ConnectAsync(
        [Uri]$target.webSocketDebuggerUrl,
        [Threading.CancellationToken]::None
    ).GetAwaiter().GetResult() | Out-Null
    Invoke-Cdp "Page.enable" | Out-Null
    Invoke-Cdp "Runtime.enable" | Out-Null

    Set-Viewport 1200 800 $false
    Invoke-Cdp "Page.navigate" @{ url = "http://localhost:3000/?job=$JobId" } | Out-Null
    Wait-JavaScript "document.querySelector('.entry-job') !== null" "public job entry"
    Save-Screenshot "01-public-job-desktop.png"

    Invoke-JavaScript "document.querySelector('.entry-job').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.chat-shell') !== null" "candidate chat"
    Invoke-JavaScript "[...document.querySelectorAll('.starter-prompts button')].find(button => button.textContent.includes('trade experience')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.job-card') !== null" "candidate recommendation" 45
    Invoke-JavaScript "[...document.querySelectorAll('.job-card button')].find(button => button.textContent.includes('Review application')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#candidate-name') !== null" "application review"
    $candidateFormScript = @"
(() => {
  const setValue = (selector, value) => {
    const input = document.querySelector(selector);
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  };
  setValue('#candidate-name', 'Browser Test Candidate');
  setValue('#candidate-contact', 'browser-candidate@example.test');
  document.querySelector('.consent-check input').click();
  document.querySelector('.application-review').requestSubmit();
  return true;
})()
"@
    Invoke-JavaScript $candidateFormScript | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar') !== null" "submitted application" 30
    Wait-JavaScript "document.querySelector('.feedback-prompt') !== null" "candidate feedback"
    Invoke-JavaScript "document.querySelector('.feedback-actions button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.feedback-prompt.complete') !== null" "candidate feedback confirmation"
    if (Invoke-JavaScript "document.querySelector('.error-notice') !== null") { throw "Candidate flow displayed an error" }
    Set-Viewport 390 760 $true
    Invoke-Cdp "Page.reload" | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar') !== null" "submitted application after phone reload"
    Wait-JavaScript "document.querySelector('.feedback-prompt.complete') !== null" "saved candidate feedback after phone reload"
    if (Invoke-JavaScript "document.querySelector('.sidebar').getBoundingClientRect().right > 0") { throw "Candidate sidebar covers the phone view" }
    Invoke-JavaScript "document.querySelector('.messages').scrollTop = document.querySelector('.messages').scrollHeight; true" | Out-Null
    Save-Screenshot "02-candidate-submitted-phone.png"

    Set-Viewport 1200 800 $false
    Invoke-JavaScript "sessionStorage.removeItem('job-talk-session'); location.href='/'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.entry-choice') !== null" "entry screen"
    Invoke-JavaScript "[...document.querySelectorAll('.entry-choice')].find(button => button.textContent.includes('I\'m hiring')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#email') !== null" "recruiter email form"
    $mailBefore = (Invoke-RestMethod -Uri "http://127.0.0.1:8025/api/v1/messages" -TimeoutSec 5).total
    $emailFormScript = @"
(() => {
  const input = document.querySelector('#email');
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '$RecruiterEmail');
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.form.requestSubmit();
  return true;
})()
"@
    Invoke-JavaScript $emailFormScript | Out-Null
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

    $codeFormScript = @"
(() => {
  const input = document.querySelector('#code');
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '$code');
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.form.requestSubmit();
  return true;
})()
"@
    Invoke-JavaScript $codeFormScript | Out-Null
    Wait-JavaScript "document.querySelector('.chat-shell') !== null" "recruiter chat" 30
    $jobChatExpression = @'
(async () => {
  const session = JSON.parse(sessionStorage.getItem('job-talk-session'));
  const headers = { Authorization: 'Bearer ' + session.access_token };
  const chats = await fetch('http://localhost:8000/api/chats', { headers }).then(response => response.json());
  const details = await Promise.all(chats.map(chat => fetch('http://localhost:8000/api/chats/' + chat.id, { headers }).then(response => response.json())));
  return details.findIndex(chat => chat.job_post?.id === __JOB_ID__);
})()
'@
    $jobChatExpression = $jobChatExpression.Replace('__JOB_ID__', $JobId)
    $jobChatIndex = Invoke-JavaScript $jobChatExpression
    if ($jobChatIndex -lt 0) { throw "Recruiter job chat was not found" }
    Invoke-JavaScript "document.querySelectorAll('.chat-row')[$jobChatIndex].click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.candidate-card') !== null" "recruiter candidate comparison" 30
    Wait-JavaScript "document.querySelector('.feedback-prompt') !== null" "recruiter feedback"
    Invoke-JavaScript "document.querySelector('.feedback-actions button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.feedback-prompt.complete') !== null" "recruiter feedback confirmation"
    if (Invoke-JavaScript "document.querySelector('.error-notice') !== null") { throw "Recruiter flow displayed an error" }
    Save-Screenshot "03-recruiter-comparison-desktop.png"
    Write-Output "Browser smoke passed: candidate phone flow and recruiter desktop comparison."
} finally {
    if ($script:socket) {
        $script:socket.Dispose()
    }
    if ($edge -and -not $edge.HasExited) {
        Stop-Process -Id $edge.Id -Force
    }
}
