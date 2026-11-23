export function statementBoardMonths(board) {
  const months=board.statement?.months?.length?board.statement.months:board.billing_months||[]
  return [...new Set([...months,
    ...(board.period_month ? [board.period_month] : [])])].filter(Boolean).sort()
}

export function statementBoardMatchesMonths(board, months) {
  return !months?.length || statementBoardMonths(board).some(month => months.includes(month))
}

export function pendingStatementTasksInScope(tasks, {months, periodNumber, subClientId, settlementScope}) {
  return (tasks || []).filter(task => months?.includes(task.month) &&
    (!periodNumber || task.period_number === periodNumber) &&
    (!subClientId || settlementScope === 'special' || task.sub_client_id === subClientId))
}
