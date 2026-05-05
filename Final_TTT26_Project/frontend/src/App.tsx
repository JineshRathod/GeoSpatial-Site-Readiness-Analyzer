import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { SecondaryPageLayout } from './components/layout/SecondaryPageLayout'
import { ThemeSync } from './components/ThemeSync'
import { ToastProvider } from './components/ui/Toast'
import { DashboardPage } from './pages/DashboardPage'
import { ProfilePage } from './pages/Profile'
import { SettingsPage } from './pages/Settings'
import Signup from './pages/Signup'
import { SignInPage } from './pages/SignInPage'

function App() {
  return (
    <BrowserRouter>
      <ThemeSync />
      <ToastProvider>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/login" element={<SignInPage />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/profile"
            element={
              <SecondaryPageLayout>
                <ProfilePage />
              </SecondaryPageLayout>
            }
          />
          <Route
            path="/settings"
            element={
              <SecondaryPageLayout>
                <SettingsPage />
              </SecondaryPageLayout>
            }
          />
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  )
}

export default App
