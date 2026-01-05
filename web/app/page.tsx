import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const quickActions = [
  { href: "/mission", label: "Run Mission", icon: "🚀", description: "Execute agent pipeline" },
  { href: "/polymarket", label: "Scan Markets", icon: "🎯", description: "Find trading opportunities" },
  { href: "/research", label: "Research", icon: "🔬", description: "Grounded deep dives" },
  { href: "/inbox", label: "Add Content", icon: "📥", description: "Save links or notes" },
];

const stats = [
  { label: "Curated Links", value: "32", icon: "📎", color: "from-purple-500 to-blue-500" },
  { label: "Evidence Items", value: "242", icon: "📦", color: "from-blue-500 to-cyan-500" },
  { label: "Categories", value: "12", icon: "🏷️", color: "from-cyan-500 to-teal-500" },
  { label: "Tasks Active", value: "5", icon: "📋", color: "from-teal-500 to-green-500" },
];

export default function Dashboard() {
  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-purple-500/20 via-blue-500/20 to-cyan-500/20 blur-3xl" />
        <div className="relative bg-zinc-900/60 backdrop-blur-xl border border-zinc-800 rounded-3xl p-8 md:p-12">
          <div className="max-w-2xl">
            <h1 className="text-5xl font-bold">
              <span className="bg-gradient-to-r from-purple-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                Good evening
              </span>
            </h1>
            <p className="text-xl text-zinc-400 mt-4 leading-relaxed">
              Your personal intelligence grows with every interaction.
              <span className="text-zinc-300"> What would you like to explore today?</span>
            </p>
          </div>

          {/* Quick Research Bar */}
          <div className="mt-8 max-w-xl">
            <div className="relative">
              <input
                type="text"
                placeholder="Ask anything — get grounded answers..."
                className="w-full bg-zinc-800/50 border border-zinc-700 rounded-2xl px-6 py-4 text-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
              />
              <button className="absolute right-2 top-1/2 -translate-y-1/2 bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 px-6 py-2 rounded-xl text-sm font-medium transition-all">
                Research
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div key={stat.label} className="group relative">
            <div className={`absolute inset-0 bg-gradient-to-r ${stat.color} rounded-2xl opacity-0 group-hover:opacity-20 transition-opacity blur-xl`} />
            <Card className="relative bg-zinc-900/80 backdrop-blur-sm border-zinc-800 hover:border-zinc-700 transition-all rounded-2xl overflow-hidden">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <span className="text-3xl">{stat.icon}</span>
                  <span className={`text-3xl font-bold bg-gradient-to-r ${stat.color} bg-clip-text text-transparent`}>
                    {stat.value}
                  </span>
                </div>
                <p className="text-sm text-zinc-500 mt-2">{stat.label}</p>
              </CardContent>
            </Card>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-xl font-semibold text-zinc-200 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {quickActions.map((action) => (
            <Link key={action.href} href={action.href} className="group">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-br from-purple-500/20 to-blue-500/20 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity blur-xl" />
                <Card className="relative bg-zinc-900/80 backdrop-blur-sm border-zinc-800 hover:border-zinc-600 transition-all rounded-2xl overflow-hidden h-full">
                  <CardContent className="p-6 text-center">
                    <div className="text-4xl mb-3 group-hover:scale-110 transition-transform">
                      {action.icon}
                    </div>
                    <h3 className="font-semibold text-zinc-100">{action.label}</h3>
                    <p className="text-sm text-zinc-500 mt-1">{action.description}</p>
                  </CardContent>
                </Card>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span>📚</span> Recent Content
            </CardTitle>
            <CardDescription>Latest additions to your library</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <RecentItem
              title="Paul Hollywood's Queen of Puddings"
              category="Baking"
              time="2h ago"
            />
            <RecentItem
              title="LangChain Agents Overview"
              category="AI/ML"
              time="5h ago"
            />
            <RecentItem
              title="Polymarket Trading Strategies"
              category="Trading"
              time="1d ago"
            />
          </CardContent>
        </Card>

        <Card className="bg-zinc-900/80 backdrop-blur-sm border-zinc-800 rounded-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span>📋</span> Active Tasks
            </CardTitle>
            <CardDescription>What you're working on</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <TaskItem title="Review earnings data" priority={1} />
            <TaskItem title="Set up Polymarket scanner" priority={2} />
            <TaskItem title="Document API endpoints" priority={2} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function RecentItem({ title, category, time }: { title: string; category: string; time: string }) {
  return (
    <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-xl hover:bg-zinc-800 transition-colors">
      <div>
        <p className="text-sm font-medium text-zinc-200">{title}</p>
        <span className="text-xs text-purple-400">{category}</span>
      </div>
      <span className="text-xs text-zinc-500">{time}</span>
    </div>
  );
}

function TaskItem({ title, priority }: { title: string; priority: number }) {
  const priorityColors = {
    1: "bg-red-500/20 text-red-400 border-red-500/30",
    2: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    3: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  };

  return (
    <div className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-xl hover:bg-zinc-800 transition-colors">
      <span className={`text-xs px-2 py-1 rounded-full border ${priorityColors[priority as keyof typeof priorityColors]}`}>
        P{priority}
      </span>
      <p className="text-sm font-medium text-zinc-200">{title}</p>
    </div>
  );
}
