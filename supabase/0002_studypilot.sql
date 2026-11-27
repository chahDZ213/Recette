-- StudyPilot — progression scolaire rattachée au compte (une ligne JSON par élève).
-- Les documents (photos, PDF) restent sur l'appareil (IndexedDB) ; seul leur
-- résultat d'analyse (texte, notions, métadonnées) est synchronisé ici.
-- À appliquer dans Supabase → SQL Editor. Rejouable.
create table if not exists public.studypilot_state (
  user_id uuid primary key references auth.users(id) on delete cascade,
  donnees jsonb       not null default '{}'::jsonb,
  maj_at  timestamptz not null default now()
);
alter table public.studypilot_state enable row level security;
drop policy if exists "studypilot: lecture" on public.studypilot_state;
drop policy if exists "studypilot: écriture" on public.studypilot_state;
drop policy if exists "studypilot: modification" on public.studypilot_state;
drop policy if exists "studypilot: suppression" on public.studypilot_state;
create policy "studypilot: lecture" on public.studypilot_state for select using (auth.uid() = user_id);
create policy "studypilot: écriture" on public.studypilot_state for insert with check (auth.uid() = user_id);
create policy "studypilot: modification" on public.studypilot_state for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "studypilot: suppression" on public.studypilot_state for delete using (auth.uid() = user_id);
