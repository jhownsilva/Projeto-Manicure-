# Studio Gel & Beauty — PWA de Salão

## Problem statement (resumo)
App PWA de agendamento e gestão para salão de beleza (manicure em gel primeiro), com painel da dona, catálogo, agendamento em 3 passos e integração WhatsApp (mockada no demo).

## Arquitetura
- Frontend: React + Tailwind + shadcn/ui, PWA (manifest + SW), react-router
- Backend: FastAPI + Motor (MongoDB), JWT auth (httpOnly cookie + Bearer)
- DB: MongoDB (users, services, bookings, clients, blocks)

## Personas
- Cliente final: agenda pelo celular em 3 passos
- Dona do salão: gerencia agenda, serviços, clientes, bloqueios

## Core requirements (estático)
- Landing com hero + galeria + catálogo
- Fluxo de agendamento em 3 telas
- Confirmação com botão WhatsApp (wa.me pré-preenchido)
- Painel admin com login: agenda dia/semana/mês, stats, bloqueios, CRUD serviços, clientes, lembretes simulados
- PWA instalável

## Feito (Fev/2026)
- Backend: auth JWT, endpoints /services, /bookings, /clients, /blocks, /stats, /reminders, /salon
- Seed admin (jonathan.alexandre20@gmail.com), serviços padrão e agendamentos demo
- Frontend: landing, catálogo, fluxo de agendamento 3 passos, painel admin (agenda, serviços, bloqueios, clientes, lembretes)
- PWA manifest + service worker

## Backlog priorizado
- P0: WhatsApp Meta Cloud API real (envio automático de confirmações/lembretes)
- P1: Cron real de lembretes (APScheduler) 1 dia antes
- P1: Multi-tenant (mesma base para várias donas)
- P2: Página de galeria dedicada com upload de fotos pelo painel
- P2: Google Calendar sync
- P2: Cobrança online via Stripe (sinal do agendamento)
