import React, { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatThread from './components/ChatThread';
import LoginScreen from './components/LoginScreen';
import ProfileModal from './components/ProfileModal';
import TasksView from './components/views/TasksView';
import PlansView from './components/views/PlansView';
import ProfilesView from './components/views/ProfilesView';
import ProfileDetailView from './components/views/ProfileDetailView';
import ReaderView from './components/views/ReaderView';
import HealthView from './components/views/HealthView';
import EmergencyView from './components/views/EmergencyView';
import ConnectorsView from './components/views/ConnectorsView';
import SettingsView from './components/views/SettingsView';
import Tutorial, { tutorialSeen, markTutorialSeen } from './components/Tutorial';
import { getConnections, setConnected, requestGoogleConsent, setToken, clearToken } from './services/connectorsService';
import { fetchAuthConfig } from './services/authService';
import { useChat, dbMsgToUiMsg } from './hooks/useChat';
import { getTheme, toggleTheme } from './services/themeService';
import { getStoredUser, signOut } from './services/authService';
import { getLocation, setStoredLocation } from './services/locationService';
import { fetchProfiles, createProfile, updateProfile, deleteProfile } from './services/profileApi';
import { fetchConversations, fetchMessages, saveMessage, deleteConversation } from './services/conversationApi';

const VIEW_TITLE = {
  tasks: 'Tasks & Reminders', plans: 'Workout & Diet Plans', reader: 'Reader',
  health: 'Health', emergency: 'Emergency', profiles: 'Care Profiles', connectors: 'Connectors', settings: 'Settings',
};

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

export default function App() {
  const [user, setUser] = useState(getStoredUser());

  const [activeView,      setActiveView]      = useState('chat');
  const [profiles,        setProfiles]        = useState([]);
  const [activeProfileId, setActiveProfileId] = useState(null);
  const [detailProfileId, setDetailProfileId] = useState(null);
  const [theme,           setTheme]           = useState(getTheme());
  const [modal,           setModal]           = useState(null);
  const [conversations,   setConversations]   = useState([]);
  const [activeConvId,    setActiveConvId]    = useState(null);
  const [loadingConv,     setLoadingConv]     = useState(false);
  const [userLocation,    setUserLocation]    = useState({ city: '', lat: null, lng: null });
  const [connections,   setConnections]   = useState({});
  const [oauthClientId, setOauthClientId] = useState('');
  const [showTutorial,  setShowTutorial]  = useState(false);

  // Resizable sidebar — width persisted, clamped to a sensible range.
  const SIDEBAR_MIN = 220, SIDEBAR_MAX = 440;
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = parseInt(localStorage.getItem('withcare-sidebar-width'), 10);
    return Number.isFinite(saved) ? Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, saved)) : 280;
  });
  const resizing = useRef(false);

  const startResize = useCallback((e) => {
    e.preventDefault();
    resizing.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    let latest = sidebarWidth;
    const onMove = (ev) => {
      if (!resizing.current) return;
      latest = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, ev.clientX));
      setSidebarWidth(latest);
    };
    const onUp = () => {
      resizing.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      try { localStorage.setItem('withcare-sidebar-width', String(Math.round(latest))); } catch (err) {}
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [sidebarWidth]);
  const healthConnected = !!connections.fit;
  const connectedKeys = Object.keys(connections).filter(k => connections[k]);

  const pendingConvId = useRef(null);
  const userId = user?.id;
  const activeProfile = profiles.find(p => p.id === activeProfileId) || profiles[0] || null;

  // Connect: request REAL Google consent for the connector's scopes, then mark connected.
  const connectConnector = useCallback(async (key) => {
    try {
      if (oauthClientId && window.google?.accounts?.oauth2) {
        // Real Google consent popup — resolves with THIS user's access token for the connector.
        const { token, expiresIn } = await requestGoogleConsent(oauthClientId, key);
        setToken(userId, key, token, expiresIn);  // scoped to this user; actions run on their account
      }
      // (no client id → dev/local: connect directly so testing still works)
      setConnected(userId, key, true);
      setConnections(getConnections(userId));
      if (key === 'fit') setActiveView('health');
    } catch (e) {
      console.warn('Connect cancelled:', e.message);  // user closed consent / not configured
    }
  }, [userId, oauthClientId]);

  const disconnectConnector = useCallback((key) => {
    setConnected(userId, key, false);
    clearToken(userId, key);
    setConnections(getConnections(userId));
    if (key === 'fit') setActiveView(v => (v === 'health' ? 'connectors' : v));
  }, [userId]);

  const handleSave = useCallback(async ({ role, content, carePlan }) => {
    if (!userId) return;
    let convId = pendingConvId.current;
    if (!convId) {
      convId = 'c-' + ((crypto.randomUUID && crypto.randomUUID()) || Math.random().toString(36).slice(2) + Date.now());
      pendingConvId.current = convId;
      setActiveConvId(convId);
      setConversations(prev => [{
        id: convId,
        title: role === 'user' ? content.slice(0, 70) : 'New conversation',
        profile_name: activeProfile?.name || 'You',
        updated_at: new Date().toISOString(),
      }, ...prev]);
    }
    await saveMessage(userId, convId, {
      role, content, carePlan,
      title: role === 'user' ? content.slice(0, 70) : undefined,
      profileName: activeProfile?.name || 'You',
    });
    if (role === 'user') {
      setConversations(prev => prev.map(c =>
        c.id === convId
          ? { ...c, title: c.title === 'New conversation' ? content.slice(0, 70) : c.title, updated_at: new Date().toISOString() }
          : c));
    }
  }, [userId, activeProfile]);

  const { messages, input, setInput, send, reset, onKey, msgVM } = useChat({
    onSave: handleSave, location: userLocation, profile: activeProfile, userId,
    connectors: connectedKeys,
  });

  useEffect(() => {
    if (!userId) return;
    fetchProfiles(userId).then(list => {
      setProfiles(list);
      setActiveProfileId(prev => prev || (list[0] && list[0].id) || null);
    });
    fetchConversations(userId).then(setConversations);
    getLocation().then(loc => { if (loc) setUserLocation(loc); });
    setConnections(getConnections(userId));
    fetchAuthConfig().then(c => setOauthClientId(c.google_client_id || ''));
    if (!tutorialSeen(userId)) setShowTutorial(true);   // first-run walkthrough
  }, [userId]);

  const closeTutorial = useCallback(() => {
    markTutorialSeen(userId);
    setShowTutorial(false);
  }, [userId]);
  const replayTutorial = useCallback(() => setShowTutorial(true), []);

  const openConversation = useCallback(async (convId) => {
    setActiveView('chat');
    if (convId === activeConvId) return;
    setLoadingConv(true);
    setActiveConvId(convId);
    pendingConvId.current = convId;
    const dbMsgs = await fetchMessages(userId, convId);
    reset(dbMsgs.map(dbMsgToUiMsg), convId);
    setLoadingConv(false);
  }, [userId, activeConvId, reset]);

  const newChat = useCallback(() => {
    setActiveView('chat');
    pendingConvId.current = null;
    setActiveConvId(null);
    reset();
  }, [reset]);

  const removeConversation = useCallback(async (convId) => {
    await deleteConversation(userId, convId);
    setConversations(prev => prev.filter(c => c.id !== convId));
    if (activeConvId === convId) newChat();
  }, [userId, activeConvId, newChat]);

  const editLocation = useCallback(() => {
    const city = window.prompt('Enter your city for "near me" searches:', userLocation.city || '');
    if (city && city.trim()) {
      const loc = { city: city.trim(), lat: null, lng: null };
      setStoredLocation(loc); setUserLocation(loc);
    }
  }, [userLocation.city]);

  const switchProfile = useCallback((profileId) => {
    setActiveProfileId(profileId); newChat();
  }, [newChat]);

  const saveProfile = useCallback(async (data) => {
    if (modal && modal !== 'new' && modal.id) {
      const updated = await updateProfile(userId, modal.id, data);
      setProfiles(prev => prev.map(p => p.id === updated.id ? updated : p));
    } else {
      const created = await createProfile(userId, data);
      setProfiles(prev => [...prev, created]);
      setActiveProfileId(created.id);
    }
    setModal(null);
  }, [userId, modal]);

  const removeProfile = useCallback(async (profileId) => {
    if (!window.confirm('Delete this care profile?')) return;
    await deleteProfile(userId, profileId);
    setProfiles(prev => prev.filter(p => p.id !== profileId));
    if (activeProfileId === profileId) setActiveProfileId(null);
  }, [userId, activeProfileId]);

  const handleSignOut = useCallback(() => {
    signOut(); setUser(null);
    setProfiles([]); setConversations([]); setActiveProfileId(null);
    pendingConvId.current = null; reset();
  }, [reset]);

  const flipTheme = useCallback(() => setTheme(toggleTheme()), []);

  // Let the Tasks / Plans pages start a chat: switch to chat view and send.
  const askFromView = useCallback((text) => {
    if (!text || !text.trim()) return;
    setActiveView('chat');
    send(text);
  }, [send]);

  // Reset profile-detail when leaving the profiles view
  useEffect(() => { if (activeView !== 'profiles') setDetailProfileId(null); }, [activeView]);

  if (!user) return <LoginScreen onLogin={setUser} />;

  // Sidebar profile view-models
  const profileVMs = profiles.map(p => {
    const isPet = p.kind === 'pet';
    const primary = isPet ? (p.species || 'Pet') : (p.relation || (p.is_self ? 'Your own care' : ''));
    const meta = [primary, p.age ? `${p.age}` : ''].filter(Boolean).join(' · ');
    return {
      id: p.id, name: p.name, relation: meta, isPet,
      initials: (p.name || '?').trim().charAt(0).toUpperCase(), photo: p.photo || '',
      active: activeProfile?.id === p.id, canEdit: true, canDelete: !p.is_self,
      onClick: () => switchProfile(p.id), onEdit: () => setModal(p), onDelete: () => removeProfile(p.id),
    };
  });

  const headerTitle = VIEW_TITLE[activeView] || (activeProfile?.name || '—');
  const headerKicker = activeView === 'chat' ? 'Managing care for' : 'Viewing';

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-on-surface font-body-md">
      <aside className="relative shrink-0 border-r border-outline-variant/60 bg-surface overflow-hidden"
             style={{ width: sidebarWidth }}>
        <Sidebar
          profiles={profileVMs} onAddProfile={() => setModal('new')}
          conversations={conversations} activeConvId={activeConvId}
          onConvClick={openConversation} onConvDelete={removeConversation} onNewChat={newChat}
          activeView={activeView} onSelectView={setActiveView}
          healthConnected={healthConnected}
          user={user} onSignOut={handleSignOut}
        />
        {/* Drag handle — resize the sidebar */}
        <div onPointerDown={startResize} title="Drag to resize" data-tour="resize"
          className="group absolute top-0 right-0 h-full w-1.5 cursor-col-resize z-20 flex justify-center hover:bg-primary/10">
          <span className="w-0.5 h-full bg-transparent group-hover:bg-primary/40 transition-colors" />
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-16 flex justify-between items-center px-6 bg-background/80 backdrop-blur-md border-b border-outline-variant/30 shrink-0 m3-enter">
          <div className="flex items-center gap-3 min-w-0">
            <Sym name={activeView === 'chat' ? 'person_pin' : 'space_dashboard'} className="text-primary text-[22px]" fill />
            <div className="min-w-0">
              <div className="text-[11px] text-on-surface-variant uppercase tracking-wide">{headerKicker}</div>
              <h2 className="font-title-lg text-[17px] text-on-surface truncate leading-tight">{headerTitle}</h2>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setActiveView('emergency')} title="Emergency & SOS"
              className="press flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-error-container text-error text-[12px] font-bold border border-error/30 hover:brightness-105">
              <Sym name="emergency" className="text-[16px]" fill /> SOS
            </button>
            <button onClick={editLocation} title="Set your location"
              className="press flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-container text-on-surface-variant text-[12px] font-medium border border-outline-variant/50 hover:bg-surface-container-high">
              <Sym name="location_on" className="text-g-red text-[16px]" />
              {userLocation.city || 'Set location'}
            </button>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-g-green-tint text-g-green-text text-[12px] font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-g-green animate-pulse" /> Connected
            </div>
            <button onClick={replayTutorial} title="How to use WithCare"
              className="press w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container transition-colors">
              <Sym name="help" className="text-[20px]" />
            </button>
            <button onClick={flipTheme} title="Toggle theme" data-tour="theme-toggle"
              className="press w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container transition-colors">
              <Sym name={theme === 'dark' ? 'light_mode' : 'dark_mode'} className="text-[20px]" />
            </button>
          </div>
        </header>

        {/* Content — animates on view change */}
        <div key={detailProfileId ? `pd-${detailProfileId}` : activeView} className="flex-1 flex flex-col min-h-0 m3-fade-through">
        {activeView === 'tasks' ? <TasksView userId={userId} onAsk={askFromView} profiles={profiles} activeProfileId={activeProfile?.id} />
          : activeView === 'plans' ? <PlansView userId={userId} onAsk={askFromView} />
          : activeView === 'reader' ? <ReaderView userId={userId} onAsk={askFromView} />
          : activeView === 'health' ? <HealthView userId={userId} profile={activeProfile} />
          : activeView === 'emergency' ? <EmergencyView userId={userId} profile={activeProfile} location={userLocation} onEditProfile={(p) => setModal(p)} onAsk={askFromView} />
          : activeView === 'profiles' ? (
              detailProfileId ? (
                <ProfileDetailView userId={userId}
                  profile={profiles.find(p => p.id === detailProfileId)}
                  onBack={() => setDetailProfileId(null)}
                  onEdit={(p) => setModal(p)}
                  onUseForChat={(id) => { switchProfile(id); }} />
              ) : (
                <ProfilesView profiles={profiles} activeProfileId={activeProfile?.id}
                  onSelect={setDetailProfileId} onAdd={() => setModal('new')} onEdit={(p) => setModal(p)} onDelete={removeProfile} />
              )
            )
          : activeView === 'connectors' ? <ConnectorsView connections={connections} clientId={oauthClientId} onConnect={connectConnector} onDisconnect={disconnectConnector} onOpenHealth={() => setActiveView('health')} />
          : activeView === 'settings' ? (
              <SettingsView user={user} userId={userId} location={userLocation} onEditLocation={editLocation} onSignOut={handleSignOut} onReplayTutorial={replayTutorial} />
            )
          : loadingConv ? (
              <div className="flex-1 flex items-center justify-center text-on-surface-variant text-sm">Loading conversation…</div>
            )
          : <ChatThread messages={messages} input={input} setInput={setInput} send={send} onKey={onKey} msgVM={msgVM} userId={userId} onOpenConnectors={() => setActiveView('connectors')} />}
        </div>
      </div>

      {modal && (
        <ProfileModal initial={modal === 'new' ? null : modal} onClose={() => setModal(null)} onSave={saveProfile} />
      )}

      {showTutorial && <Tutorial onClose={closeTutorial} onNavigate={setActiveView} />}
    </div>
  );
}
