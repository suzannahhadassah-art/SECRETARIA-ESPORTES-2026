Set-Location $PSScriptRoot

Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "   Secretaria de Esportes e Lazer - Acesso Externo" -ForegroundColor Cyan
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""

# Para processos anteriores
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Inicia o sistema Flask em segundo plano
Write-Host "  Iniciando o sistema..." -ForegroundColor White
$python = "C:\Users\ebuta\AppData\Local\Programs\Python\Python312\python.exe"
Start-Process -FilePath $python -ArgumentList "app.py" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
Start-Sleep -Seconds 5
Write-Host "  Sistema iniciado em http://localhost:5000" -ForegroundColor Green
Write-Host ""

# Arquivo temporario para capturar saida do cloudflared
$logFile = "$PSScriptRoot\cloudflared_log.txt"
if (Test-Path $logFile) { Remove-Item $logFile }

Write-Host "  Conectando ao Cloudflare..." -ForegroundColor White
Write-Host "  Aguarde o link publico aparecer..." -ForegroundColor Gray
Write-Host ""

# Inicia cloudflared redirecionando stderr para o arquivo de log
$cf = Start-Process -FilePath "$PSScriptRoot\cloudflared.exe" `
    -ArgumentList "tunnel --url http://localhost:5000" `
    -RedirectStandardError $logFile `
    -NoNewWindow -PassThru

# Aguarda o link aparecer no log (ate 30s)
$url = $null
$timeout = 0
while (-not $url -and $timeout -lt 30) {
    Start-Sleep -Seconds 1
    $timeout++
    if (Test-Path $logFile) {
        $content = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
        if ($content -match 'https://[a-z0-9\-]+\.trycloudflare\.com') {
            $url = $Matches[0]
        }
    }
}

if ($url) {
    # Salva o link em arquivo de texto
    $url | Out-File "$PSScriptRoot\link_acesso.txt" -Encoding UTF8

    # Copia para a area de transferencia
    $url | Set-Clipboard

    Write-Host ""
    Write-Host "  ================================================" -ForegroundColor Green
    Write-Host "   LINK PUBLICO DO SISTEMA:" -ForegroundColor Green
    Write-Host ""
    Write-Host "   $url" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   Link copiado para a area de transferencia!" -ForegroundColor Green
    Write-Host "   Link salvo em: link_acesso.txt" -ForegroundColor Green
    Write-Host "  ================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Envie esse link para os professores." -ForegroundColor White
    Write-Host "  Funciona de qualquer lugar com internet." -ForegroundColor Gray
    Write-Host ""
    Write-Host "  IMPORTANTE: O link muda cada vez que voce" -ForegroundColor Yellow
    Write-Host "  reiniciar este programa. Mantenha esta" -ForegroundColor Yellow
    Write-Host "  janela aberta enquanto os professores acessam." -ForegroundColor Yellow
    Write-Host ""

    # Abre o link no navegador
    Start-Process $url

} else {
    Write-Host "  Nao foi possivel obter o link do Cloudflare." -ForegroundColor Red
    Write-Host "  Verifique sua conexao com a internet e tente novamente." -ForegroundColor Red
}

Write-Host ""
Write-Host "  Pressione qualquer tecla para encerrar o acesso externo..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Encerra cloudflared ao fechar
if ($cf -and !$cf.HasExited) { $cf.Kill() }
if (Test-Path $logFile) { Remove-Item $logFile -ErrorAction SilentlyContinue }
Write-Host ""
Write-Host "  Acesso externo encerrado." -ForegroundColor Cyan
