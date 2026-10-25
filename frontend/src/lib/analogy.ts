export function parseExpression(expression: string): { positive: string[]; negative: string[] } {
  const tokens = expression.trim().split(/\s+/)
  if (!tokens.length || !tokens[0] || tokens.length % 2 === 0) throw new Error('请用空格分隔词与运算符，例如 king - man + woman')
  const positive: string[] = [], negative: string[] = []
  for (let i = 0; i < tokens.length; i += 2) {
    const word = tokens[i]!
    if (word === '+' || word === '-') throw new Error('运算符之间需要一个词')
    const operator = i === 0 ? '+' : tokens[i - 1]
    if (operator !== '+' && operator !== '-') throw new Error('只支持 + 和 -，请在运算符两侧加空格')
    ;(operator === '+' ? positive : negative).push(word)
  }
  if (positive.length + negative.length > 10) throw new Error('最多输入 10 个词')
  return { positive, negative }
}
