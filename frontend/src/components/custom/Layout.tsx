import { Outlet, Link, NavLink } from 'react-router-dom';
import { useAuth } from '@/context/auth';
import { Button } from '@/components/ui/button';
import { LogOut, BookOpen, PenTool, LayoutDashboard, User, History, FileText, Wallet, ListChecks } from 'lucide-react';
import { cn } from '@/lib/utils';

export const Layout = () => {
  const { logout, user } = useAuth();

  const navItems = [
    { href: '/', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/generate', label: 'Generator', icon: PenTool },
    { href: '/knowledge', label: 'Knowledge Base', icon: BookOpen },
    { href: '/profiles', label: 'Style Profiles', icon: User },
    { href: '/drafts', label: 'Drafts', icon: FileText },
    { href: '/runs', label: 'Runs', icon: ListChecks },
    { href: '/costs', label: 'Spending', icon: Wallet },
    { href: '/history', label: 'Earlier articles', icon: History },
  ];

  return (
    <div className="min-h-screen flex bg-zinc-50 dark:bg-zinc-950">
      {/* Sidebar */}
      <aside className="w-64 bg-white dark:bg-zinc-900 border-r border-zinc-200 dark:border-zinc-800 hidden md:flex flex-col fixed h-full z-10">
        <div className="p-6 border-b border-zinc-200 dark:border-zinc-800">
          <Link to="/" className="flex items-center gap-2 font-bold text-xl text-zinc-900 dark:text-zinc-50">
            <div className="bg-primary text-primary-foreground p-1.5 rounded-md">
              <PenTool className="h-5 w-5" />
            </div>
            <span>ContentStrat</span>
          </Link>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-50"
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center gap-3 px-3 py-2 mb-2">
            <div className="h-8 w-8 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center">
              <User className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50 truncate">
                {user?.email || 'User'}
              </p>
              <Link className="text-xs text-zinc-500 underline" to="/costs">Generation spending</Link>
            </div>
          </div>
          <Button 
            variant="outline" 
            className="w-full justify-start text-zinc-600 dark:text-zinc-400" 
            onClick={logout}
          >
            <LogOut className="h-4 w-4 mr-2" />
            Logout
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 md:ml-64 min-h-screen flex flex-col">
        {/* Mobile Header */}
        <header className="md:hidden h-16 border-b bg-white dark:bg-zinc-900 flex items-center px-4 justify-between sticky top-0 z-20">
           <Link to="/" className="font-bold text-lg">ContentStrat</Link>
           <details className="relative"><summary className="cursor-pointer rounded border px-3 py-2 text-sm">Menu</summary><nav className="absolute right-0 mt-2 w-56 bg-white dark:bg-zinc-900 border rounded-lg p-2 shadow-lg">{navItems.map(item => <Link key={item.href} className="block p-3 text-sm hover:bg-muted" to={item.href} onClick={event => event.currentTarget.closest('details')?.removeAttribute('open')}>{item.label}</Link>)}<Button variant="ghost" onClick={logout}>Logout</Button></nav></details>
        </header>

        <div className="flex-1 p-4 md:p-8 overflow-auto">
          <div className="max-w-6xl mx-auto">
             <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
};
