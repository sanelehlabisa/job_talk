# Uses the signed-in test recruiter's session only; creates/changes no jobs or applications.
Invoke-JavaScript @'
(() => {
  window.__logoutToken=JSON.parse(sessionStorage.getItem('job-talk-session')).access_token;
  window.__logoutFetch=window.fetch.bind(window);
  window.fetch=(url, options)=>String(url).endsWith('/auth/logout')
    ? Promise.reject(new TypeError('Simulated offline logout'))
    : window.__logoutFetch(url, options);
  document.querySelector('button[aria-label="Log out"]').click();
  return true;
})()
'@ | Out-Null
try {
    Wait-JavaScript "document.body.textContent.includes('Sign out could not finish')" 'visible logout failure'
    if (-not (Invoke-JavaScript "!!sessionStorage.getItem('job-talk-session') && !!document.querySelector('.app-layout')")) {
        throw 'Offline logout silently discarded a still-valid session'
    }
    Invoke-JavaScript @'
(() => {
  window.fetch=window.__logoutFetch;
  [...document.querySelectorAll('[role="alert"] button')].find(button=>button.textContent.includes('Retry')).click();
  return true;
})()
'@ | Out-Null
    Wait-JavaScript "!sessionStorage.getItem('job-talk-session') && !!document.querySelector('.entry-choice')" 'successful logout'
    $status = Invoke-JavaScript @'
fetch('http://localhost:8000/api/chats', {headers:{Authorization:'Bearer '+window.__logoutToken}})
  .then(response=>response.status)
'@
    if ($status -ne 401) { throw 'Logged-out token can still access private chats' }
    Write-Output 'Logout browser check passed: offline failure stays visible, retry signs out, browser clears session, token replay returns 401.'
} finally {
    Invoke-JavaScript @'
(async () => {
  window.fetch=window.__logoutFetch;
  await fetch('http://localhost:8000/api/auth/logout', {method:'POST',headers:{Authorization:'Bearer '+window.__logoutToken}});
  delete window.__logoutToken;
  delete window.__logoutFetch;
  return true;
})()
'@ | Out-Null
}
