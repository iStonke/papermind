export function providerLabel(provider) {
  return { ollama: 'Lokal', openai: 'OpenAI', anthropic: 'Claude' }[provider] || 'KI';
}
