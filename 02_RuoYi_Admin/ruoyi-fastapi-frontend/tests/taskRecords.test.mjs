import test from 'node:test'
import assert from 'node:assert/strict'
import { filterTaskRecords, recordsToCsv } from '../src/utils/taskRecords.js'

const tasks = [
  { taskCode: 'TASK_A', algorithmId: 'ice', status: 'submitted', region: '沈阳', createTime: '2026-10-01 00:00:00' },
  { taskCode: 'TASK_B', algorithmId: 'ice', status: 'queued', region: '沈阳', createTime: '2026-10-06 23:59:59' },
  { taskCode: 'TASK_C', algorithmId: 'wind', status: 'running', region: '大连', createTime: '2026-10-07 00:00:00' },
  { taskCode: 'TASK_D', algorithmId: 'ice', status: 'stopped', region: '沈阳', createTime: '' }
]

test('running filter includes queued and submitted; dates include both whole boundary days', () => {
  const rows = filterTaskRecords(tasks, { status: 'running', algorithmId: 'ice', region: ' 沈阳 ', createDateRange: ['2026-10-01', '2026-10-06'] })
  assert.deepEqual(rows.map(row => row.taskCode), ['TASK_A', 'TASK_B'])
})

test('cleared dates and stopped status work with a case-insensitive keyword', () => {
  assert.equal(filterTaskRecords(tasks, { createDateRange: null }).length, 4)
  assert.deepEqual(filterTaskRecords(tasks, { keyword: ' task_d ', status: 'stopped' }), [tasks[3]])
})

test('CSV preserves Chinese, zero, commas, quotes and multiline errors', () => {
  assert.equal(recordsToCsv(['名称', '进度', '错误'], [['沈阳,线路"一"', 0, '第一行\n第二行']]),
    '\uFEFF"名称","进度","错误"\r\n"沈阳,线路""一""","0","第一行\n第二行"')
})

test('CSV neutralizes formula prefixes including leading whitespace', () => {
  const csv = recordsToCsv(['值'], [['=1+1'], [' +SUM(A1)'], ['\t@command'], ['-1'], [null]])
  assert.ok(csv.includes('"\'=1+1"'))
  assert.ok(csv.includes('"\' +SUM(A1)"'))
  assert.ok(csv.includes('"\'\t@command"'))
  assert.ok(csv.includes('"\'-1"'))
  assert.ok(csv.endsWith('""'))
})
