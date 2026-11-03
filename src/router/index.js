import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/auth/LoginPage.vue'),
    meta: { layout: 'auth', guestOnly: true, titleKey: 'nav.login' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/pages/auth/RegisterPage.vue'),
    meta: { layout: 'auth', guestOnly: true, titleKey: 'nav.register' },
  },
  {
    path: '/forgot-password',
    name: 'forgot-password',
    component: () => import('@/pages/auth/ForgotPasswordPage.vue'),
    meta: { layout: 'auth', titleKey: 'auth.forgotTitle' },
  },
  {
    path: '/pending',
    name: 'pending',
    component: () => import('@/pages/PendingPage.vue'),
    meta: { requiresAuth: true, titleKey: 'auth.pending' },
  },
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/HomePage.vue'),
    meta: { titleKey: 'nav.home' },
  },
  {
    path: '/discover',
    name: 'discover',
    component: () => import('@/pages/DiscoverPage.vue'),
    meta: { titleKey: 'nav.discover' },
  },
  {
    path: '/algorithms',
    name: 'algorithms',
    component: () => import('@/pages/AlgorithmsPage.vue'),
    meta: { titleKey: 'nav.algorithms' },
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('@/pages/SearchPage.vue'),
    meta: { titleKey: 'common.search' },
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: () => import('@/pages/NotificationsPage.vue'),
    meta: { requiresAuth: true, titleKey: 'nav.notifications' },
  },
  {
    path: '/feedback',
    name: 'feedback',
    component: () => import('@/pages/FeedbackPage.vue'),
    meta: { requiresAuth: true, titleKey: 'nav.feedback' },
  },
  {
    path: '/categories/:slug',
    name: 'category',
    component: () => import('@/pages/CategoryPage.vue'),
    meta: { titleKey: 'discover.categories' },
  },
  {
    path: '/tags/:slug',
    name: 'tag',
    component: () => import('@/pages/TagPage.vue'),
    meta: { titleKey: 'discover.hotTags' },
  },
  {
    path: '/items/new',
    name: 'item-new',
    component: () => import('@/pages/ItemEditorPage.vue'),
    meta: { requiresAuth: true, requiresActive: true, titleKey: 'item.newTitle' },
  },
  {
    path: '/items/:id',
    name: 'item-detail',
    component: () => import('@/pages/ItemDetailPage.vue'),
    meta: { titleKey: 'item.detailEyebrow' },
  },
  {
    path: '/me',
    name: 'me',
    component: () => import('@/pages/MePage.vue'),
    meta: { requiresAuth: true, titleKey: 'nav.me' },
  },
  {
    path: '/settings/profile',
    name: 'settings-profile',
    component: () => import('@/pages/settings/ProfileSettingsPage.vue'),
    meta: { requiresAuth: true, titleKey: 'nav.profile' },
  },
  {
    path: '/settings/security',
    name: 'settings-security',
    component: () => import('@/pages/settings/SecuritySettingsPage.vue'),
    meta: { requiresAuth: true, titleKey: 'nav.security' },
  },
  {
    path: '/settings/notifications',
    name: 'settings-notifications',
    component: () => import('@/pages/settings/NotificationSettingsPage.vue'),
    meta: { requiresAuth: true, titleKey: 'nav.push' },
  },
  {
    path: '/s/:code',
    name: 'share',
    component: () => import('@/pages/SharePage.vue'),
    meta: { titleKey: 'common.share' },
  },
  {
    path: '/admin',
    component: () => import('@/components/admin/AdminLayout.vue'),
    meta: { requiresAuth: true, admin: true },
    children: [
      {
        path: '',
        name: 'admin-dashboard',
        component: () => import('@/pages/admin/AdminDashboardPage.vue'),
        meta: { requiresAuth: true, admin: true, titleKey: 'admin.overview' },
      },
      {
        path: 'users',
        name: 'admin-users',
        component: () => import('@/pages/admin/AdminUsersPage.vue'),
        meta: { requiresAuth: true, admin: true, titleKey: 'admin.users' },
      },
      {
        path: 'feedback',
        name: 'admin-feedback',
        component: () => import('@/pages/admin/AdminFeedbackPage.vue'),
        meta: { requiresAuth: true, admin: true, titleKey: 'admin.feedback' },
      },
      {
        path: 'reports',
        name: 'admin-reports',
        component: () => import('@/pages/admin/AdminReportsPage.vue'),
        meta: { requiresAuth: true, admin: true, titleKey: 'admin.reports' },
      },
      {
        path: 'analytics',
        name: 'admin-analytics',
        component: () => import('@/pages/admin/AdminAnalyticsPage.vue'),
        meta: { requiresAuth: true, admin: true, titleKey: 'admin.analytics' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: { titleKey: 'errors.notFound' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, top: 88, behavior: 'smooth' }
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.ensureSession()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return auth.isPending ? { name: 'pending' } : { name: 'home' }
  }
  if (to.meta.admin && !auth.isAdmin) {
    return { name: 'home' }
  }
  if (auth.isPending && to.meta.requiresActive) {
    return { name: 'pending' }
  }
  return true
})

export default router
