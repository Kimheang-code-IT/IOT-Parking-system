export function exportToCSV(data: Record<string, any>[], filename: string) {
  if (!data.length) return

  const headers = Object.keys(data[0]!)
  const csvRows = [
    headers.join(','), // header row
    ...data.map(row => 
      headers.map(fieldName => {
        const value = row[fieldName] ?? ''
        const escaped = ('' + value).replace(/"/g, '""')
        return `"${escaped}"`
      }).join(',')
    )
  ]

  const csvContent = csvRows.join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
