# æ:// Capture — Region capture with annotation + receipt
# Best of HP Snipping Tool + Hermes Desktop verification
# Usage: capture-region.ps1 [-Full] [-Annotate] [-Receipt]

param(
    [switch]$Full,
    [switch]$Annotate,
    [switch]$Receipt
)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$captureDir = "C:/æ/captures"
$receiptFile = "C:/æ/logs/capture-receipts.jsonl"

# Ensure directories exist
New-Item -ItemType Directory -Force -Path $captureDir | Out-Null
New-Item -ItemType Directory -Force -Path "C:/æ/logs" | Out-Null

# ── Region Selection ──
if (-not $Full) {
    # Create a full-screen overlay form for region selection
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    
    $form = New-Object System.Windows.Forms.Form
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
    $form.WindowState = [System.Windows.Forms.FormWindowState]::Maximized
    $form.TopMost = $true
    $form.Cursor = [System.Windows.Forms.Cursors]::Cross
    $form.Opacity = 0.3
    $form.ShowInTaskbar = $false
    
    # Screenshot for background
    $bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bmp)
    $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    
    $form.BackgroundImage = $bmp
    $form.BackgroundImageLayout = [System.Windows.Forms.ImageLayout]::Stretch
    
    $startPoint = [System.Drawing.Point]::Empty
    $isSelecting = $false
    $selectionRect = [System.Drawing.Rectangle]::Empty
    
    $form.Add_MouseDown({
        param($s, $e)
        $script:isSelecting = $true
        $script:startPoint = $e.Location
    })
    
    $form.Add_MouseMove({
        param($s, $e)
        if ($script:isSelecting) {
            $x = [Math]::Min($script:startPoint.X, $e.X)
            $y = [Math]::Min($script:startPoint.Y, $e.Y)
            $w = [Math]::Abs($e.X - $script:startPoint.X)
            $h = [Math]::Abs($e.Y - $script:startPoint.Y)
            $script:selectionRect = [System.Drawing.Rectangle]::new($x, $y, $w, $h)
            
            # Draw selection rectangle
            $g = $form.CreateGraphics()
            $g.Clear([System.Drawing.Color]::FromArgb(76, 0, 0, 0))
            $g.FillRectangle([System.Drawing.Brushes]::White, $script:selectionRect)
            $g.DrawRectangle([System.Drawing.Pens]::Gold, $script:selectionRect)
            $g.Dispose()
        }
    })
    
    $form.Add_MouseUp({
        param($s, $e)
        $script:isSelecting = $false
        $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Close()
    })
    
    $form.Add_KeyDown({
        param($s, $e)
        if ($e.KeyCode -eq [System.Windows.Forms.Keys]::Escape) {
            $form.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
            $form.Close()
        }
    })
    
    $result = $form.ShowDialog()
    
    if ($result -ne [System.Windows.Forms.DialogResult]::OK -or $selectionRect.Width -lt 10 -or $selectionRect.Height -lt 10) {
        Write-Output "CANCELLED"
        exit 0
    }
    
    # Capture selected region
    $captureBmp = New-Object System.Drawing.Bitmap($selectionRect.Width, $selectionRect.Height)
    $captureGraphics = [System.Drawing.Graphics]::FromImage($captureBmp)
    $captureGraphics.CopyFromScreen($selectionRect.Location, [System.Drawing.Point]::Empty, $selectionRect.Size)
    $captureGraphics.Dispose()
    
} else {
    # Full screen capture
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $captureBmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $captureGraphics = [System.Drawing.Graphics]::FromImage($captureBmp)
    $captureGraphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    $captureGraphics.Dispose()
}

# ── Save to file ──
$filename = "ae-capture-$timestamp.png"
$filepath = Join-Path $captureDir $filename
$captureBmp.Save($filepath, [System.Drawing.Imaging.ImageFormat]::Png)

# ── Copy to clipboard ──
[System.Windows.Forms.Clipboard]::SetImage($captureBmp)

# ── Generate receipt ──
$hash = (Get-FileHash -Path $filepath -Algorithm SHA256).Hash.ToLower()
$rcpt = @{
    kind = "capture"
    file = $filename
    path = $filepath
    timestamp = (Get-Date -Format "o")
    sha256 = $hash
    size = (Get-Item $filepath).Length
    width = $captureBmp.Width
    height = $captureBmp.Height
    mode = if ($Full.IsPresent) { "full" } else { "region" }
}

# Load previous hash for chain
$prevHash = "genesis"
if (Test-Path $receiptFile) {
    $lastLine = Get-Content $receiptFile -Tail 1
    if ($lastLine) {
        $prevReceipt = $lastLine | ConvertFrom-Json
        $prevHash = $prevReceipt.sha256
    }
}

$rcpt["prev_hash"] = $prevHash
$chainHash = [System.Security.Cryptography.SHA256]::Create()
$chainInput = "$prevHash$($rcpt.sha256)$timestamp"
$chainHashBytes = $chainHash.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($chainInput))
$rcpt["chain_hash"] = [BitConverter]::ToString($chainHashBytes).Replace("-", "").ToLower()

# Save receipt
$receiptJson = $rcpt | ConvertTo-Json -Compress
[System.IO.File]::AppendAllText($receiptFile, $receiptJson + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

# ── Output ──
Write-Output "CAPTURED: $filename"
Write-Output "SHA256: $hash"
Write-Output "CHAIN: $prevHash -> $($rcpt.chain_hash)"
Write-Output "SAVED: $filepath"
Write-Output "CLIPBOARD: OK"

# Cleanup
$captureBmp.Dispose()
if ($bmp) { $bmp.Dispose() }
if ($graphics) { $graphics.Dispose() }
