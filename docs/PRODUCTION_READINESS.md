# Pensy Platform - Production Readiness Checklist

## Before Going Live

### Security
- [ ] Change JWT_SECRET_KEY to a cryptographically random value
- [ ] Configure proper CORS origins (not wildcard)
- [ ] Enable HTTPS/TLS termination (nginx or load balancer)
- [ ] Rotate API keys regularly
- [ ] Review and restrict Binance API key permissions (trade-only, IP whitelist)
- [ ] Implement API rate limiting on endpoints
- [ ] Review RBAC roles and restrict access

### Infrastructure
- [ ] Use managed PostgreSQL (RDS, Cloud SQL)
- [ ] Use managed Redis (ElastiCache, Memorystore)
- [ ] Set up database backups
- [ ] Configure monitoring and alerting (Prometheus + Grafana)
- [ ] Set up log aggregation (ELK, CloudWatch)
- [ ] Configure health check probes in deployment
- [ ] Set resource limits (CPU, memory)

### Trading Safety
- [ ] Verify all risk limits are appropriate for production
- [ ] Test kill switch end-to-end
- [ ] Test live mode confirmation flow
- [ ] Run reconciliation against exchange in staging
- [ ] Verify paper and live orders never mix
- [ ] Test exchange disconnect handling
- [ ] Test order timeout and retry behavior
- [ ] Verify idempotency (duplicate client_order_id rejection)

### Operational
- [ ] Set up alert channels (Slack, Telegram, PagerDuty)
- [ ] Create runbook for common incidents
- [ ] Document exchange-specific quirks
- [ ] Test disaster recovery (DB restore, service restart with open orders)
- [ ] Set up audit log retention policy
- [ ] Configure log rotation

### Legal/Compliance
- [ ] Review local regulations for automated trading
- [ ] Understand exchange terms of service
- [ ] Consider licensing requirements
- [ ] Implement required record-keeping

## NOT Suitable For
- High-frequency trading (latency not optimized)
- Multi-tenant operation (single-operator design)
- Unattended live trading without monitoring
