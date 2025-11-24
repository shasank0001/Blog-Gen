import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { FileText, Plus, TrendingUp, Users, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getThreads, getBins } from '@/lib/api';

interface Thread {
  id: string;
  topic: string;
  status: string;
  created_at: string;
}

export const Dashboard = () => {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [binsCount, setBinsCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [threadsData, binsData] = await Promise.all([
          getThreads(),
          getBins()
        ]);
        setThreads(threadsData);
        setBinsCount(binsData.length);
      } catch (error) {
        console.error("Failed to fetch dashboard data", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const recentThreads = threads.slice(0, 5);

  const formatTimeAgo = (dateString: string) => {
      const date = new Date(dateString);
      const now = new Date();
      const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
      
      let interval = seconds / 31536000;
      if (interval > 1) return Math.floor(interval) + " years ago";
      interval = seconds / 2592000;
      if (interval > 1) return Math.floor(interval) + " months ago";
      interval = seconds / 86400;
      if (interval > 1) return Math.floor(interval) + " days ago";
      interval = seconds / 3600;
      if (interval > 1) return Math.floor(interval) + " hours ago";
      interval = seconds / 60;
      if (interval > 1) return Math.floor(interval) + " minutes ago";
      return Math.floor(seconds) + " seconds ago";
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Overview of your content generation and knowledge base.
          </p>
        </div>
        <Link to="/generate">
          <Button size="lg" className="gap-2">
            <Plus className="h-4 w-4" /> New Article
          </Button>
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Articles</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{loading ? "..." : threads.length}</div>
            <p className="text-xs text-muted-foreground">
              Lifetime generated articles
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Knowledge Bins</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{loading ? "..." : binsCount}</div>
            <p className="text-xs text-muted-foreground">
              Active knowledge sources
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Words Generated</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">--</div>
            <p className="text-xs text-muted-foreground">
              Not available yet
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>Recent Articles</CardTitle>
            <CardDescription>
              You have {threads.length} articles in total.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-8">
              {loading ? (
                <div className="text-center py-4 text-muted-foreground">Loading...</div>
              ) : recentThreads.length === 0 ? (
                <div className="text-center py-4 text-muted-foreground">No articles yet. Create one!</div>
              ) : (
                recentThreads.map((item) => (
                  <div key={item.id} className="flex items-center">
                    <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                      <FileText className="h-4 w-4 text-primary" />
                    </div>
                    <div className="ml-4 space-y-1">
                      <p className="text-sm font-medium leading-none">{item.topic}</p>
                      <p className="text-xs text-muted-foreground">{formatTimeAgo(item.created_at)}</p>
                    </div>
                    <div className="ml-auto font-medium text-sm">
                      {item.status === 'completed' ? (
                        <span className="text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400 px-2 py-1 rounded-full text-xs">
                          Completed
                        </span>
                      ) : item.status === 'failed' ? (
                         <span className="text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-400 px-2 py-1 rounded-full text-xs">
                          Failed
                        </span>
                      ) : (
                        <span className="text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30 dark:text-yellow-400 px-2 py-1 rounded-full text-xs">
                          {item.status}
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
        
        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>
              Common tasks and shortcuts.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
             <Link to="/knowledge">
                <Button variant="outline" className="w-full justify-start h-auto py-4 px-4">
                    <div className="h-10 w-10 rounded bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mr-4">
                        <Users className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    </div>
                    <div className="text-left">
                        <div className="font-semibold">Manage Knowledge</div>
                        <div className="text-xs text-muted-foreground">Upload docs & create bins</div>
                    </div>
                    <ArrowRight className="ml-auto h-4 w-4 text-muted-foreground" />
                </Button>
             </Link>
             <Link to="/generate">
                <Button variant="outline" className="w-full justify-start h-auto py-4 px-4">
                    <div className="h-10 w-10 rounded bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center mr-4">
                        <TrendingUp className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                    </div>
                    <div className="text-left">
                        <div className="font-semibold">Analyze Style</div>
                        <div className="text-xs text-muted-foreground">Check your brand voice</div>
                    </div>
                    <ArrowRight className="ml-auto h-4 w-4 text-muted-foreground" />
                </Button>
             </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
