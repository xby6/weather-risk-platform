export function filterTaskRecords(tasks, query) {
  const keyword = String(query.keyword || '').trim().toLocaleLowerCase()
  const region = String(query.region || '').trim()
  const range = query.createDateRange || []
  return tasks.filter(task => {
    const keywordHit = !keyword || [task.taskCode, task.taskName, task.lineCode, task.algorithmName]
      .some(value => String(value || '').toLocaleLowerCase().includes(keyword))
    const statusHit = !query.status || (query.status === 'running'
      ? ['running', 'queued', 'submitted'].includes(task.status)
      : task.status === query.status)
    const algorithmHit = !query.algorithmId || task.algorithmId === query.algorithmId
    const regionHit = !region || String(task.region || '').includes(region)
    const day = String(task.createTime || '').slice(0, 10)
    const dateHit = range.length !== 2 || (day >= range[0] && day <= range[1])
    return keywordHit && statusHit && algorithmHit && regionHit && dateHit
  })
}

export function recordsToCsv(headers, rows) {
  const cell = value => {
    let text = String(value ?? '')
    // Spreadsheet applications interpret these prefixes as formulas, even in quoted CSV cells.
    if (/^\s*[=+@-]/.test(text)) text = `'${text}`
    return `"${text.replace(/"/g, '""')}"`
  }
  return '\uFEFF' + [headers, ...rows].map(row => row.map(cell).join(',')).join('\r\n')
}
