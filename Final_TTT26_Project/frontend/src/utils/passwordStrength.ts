export type PasswordStrengthLevel = 'weak' | 'medium' | 'strong'

export function getPasswordStrength(password: string): PasswordStrengthLevel {
  if (!password) return 'weak'
  let s = 0
  if (password.length >= 8) s++
  if (password.length >= 12) s++
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) s++
  if (/\d/.test(password)) s++
  if (/[^A-Za-z0-9]/.test(password)) s++
  if (s <= 2) return 'weak'
  if (s <= 4) return 'medium'
  return 'strong'
}
