# Konversi laporan .docx -> .pdf memakai Microsoft Word (COM),
# sekaligus memperbarui daftar isi (TOC) agar nomor halaman terisi.
$ErrorActionPreference = "Stop"
$docx = "C:\Users\kdkly\Documents\erp-bakery\docs\Laporan_UTS_EIS_ERP_Bakery.docx"
$pdf  = "C:\Users\kdkly\Documents\erp-bakery\docs\Laporan_UTS_EIS_ERP_Bakery.pdf"

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

$doc = $word.Documents.Open($docx, $false, $false)
$doc.Fields.Update() | Out-Null
foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
$doc.Repaginate()
$pages = $doc.ComputeStatistics(2)   # wdStatisticPages
$doc.Save()
$doc.ExportAsFixedFormat($pdf, 17)   # wdExportFormatPDF
$doc.Close(0)
$word.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null

Write-Output "PAGES=$pages"
Write-Output "PDF=$pdf"
