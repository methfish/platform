import { useState, FormEvent } from 'react';
import { Send } from 'lucide-react';
import { useCreateOrder } from '../../hooks/useOrders';
import { OrderCreateRequest, OrderSide, OrderType, TimeInForce } from '../../types/order';
import {
  ASSET_CLASSES,
  AssetClass,
  SYMBOLS_BY_CLASS,
  EXCHANGE_FOR_CLASS,
  ASSET_CLASS_COLORS,
  ORDER_TYPES,
  ORDER_SIDES,
  TIME_IN_FORCES,
} from '../../utils/constants';

export default function OrderForm() {
  const createOrder = useCreateOrder();

  const [assetClass, setAssetClass] = useState<AssetClass>('crypto');

  const [form, setForm] = useState({
    exchange: EXCHANGE_FOR_CLASS['crypto'],
    symbol: SYMBOLS_BY_CLASS['crypto'][0].symbol,
    side: 'buy' as OrderSide,
    type: 'market' as OrderType,
    quantity: '',
    price: '',
    stop_price: '',
    time_in_force: 'gtc' as TimeInForce,
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleAssetClassChange = (cls: AssetClass) => {
    setAssetClass(cls);
    setForm((f) => ({
      ...f,
      exchange: EXCHANGE_FOR_CLASS[cls],
      symbol: SYMBOLS_BY_CLASS[cls][0].symbol,
    }));
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    const qty = parseFloat(form.quantity);
    if (!form.quantity || isNaN(qty) || qty <= 0) {
      newErrors.quantity = 'Valid quantity required';
    }

    if (form.type === 'limit' || form.type === 'stop_limit') {
      const price = parseFloat(form.price);
      if (!form.price || isNaN(price) || price <= 0) {
        newErrors.price = 'Valid price required for limit orders';
      }
    }

    if (form.type === 'stop' || form.type === 'stop_limit') {
      const stopPrice = parseFloat(form.stop_price);
      if (!form.stop_price || isNaN(stopPrice) || stopPrice <= 0) {
        newErrors.stop_price = 'Valid stop price required';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const order: OrderCreateRequest = {
      exchange: form.exchange,
      symbol: form.symbol,
      side: form.side,
      type: form.type,
      quantity: parseFloat(form.quantity),
      time_in_force: form.time_in_force,
    };

    if (form.type === 'limit' || form.type === 'stop_limit') {
      order.price = parseFloat(form.price);
    }
    if (form.type === 'stop' || form.type === 'stop_limit') {
      order.stop_price = parseFloat(form.stop_price);
    }

    createOrder.mutate(order, {
      onSuccess: () => {
        setForm((f) => ({ ...f, quantity: '', price: '', stop_price: '' }));
      },
    });
  };

  const updateField = (field: string, value: string) => {
    setForm((f) => ({ ...f, [field]: value }));
    if (errors[field]) {
      setErrors((e) => {
        const next = { ...e };
        delete next[field];
        return next;
      });
    }
  };

  const colors = ASSET_CLASS_COLORS[assetClass];
  const symbolOptions = SYMBOLS_BY_CLASS[assetClass];

  return (
    <form onSubmit={handleSubmit} className="card">
      <h3 className="text-sm font-semibold text-gray-200 mb-4">New Order</h3>

      {/* Asset Class Selector */}
      <div className="flex gap-2 mb-4">
        {ASSET_CLASSES.map((cls) => {
          const c = ASSET_CLASS_COLORS[cls.value as AssetClass];
          const active = assetClass === cls.value;
          return (
            <button
              key={cls.value}
              type="button"
              onClick={() => handleAssetClassChange(cls.value as AssetClass)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                active
                  ? `${c.bg} ${c.text} ${c.border}`
                  : 'bg-surface text-gray-500 border-surface-border hover:text-gray-300'
              }`}
            >
              {cls.label}
            </button>
          );
        })}
        <span className={`ml-2 self-center text-[10px] px-2 py-0.5 rounded border ${colors.bg} ${colors.text} ${colors.border}`}>
          {assetClass === 'crypto' ? 'Paper / Binance' : assetClass === 'forex' ? 'Simulated FX' : 'Alpaca Paper'}
        </span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Symbol */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Symbol</label>
          <select
            value={form.symbol}
            onChange={(e) => updateField('symbol', e.target.value)}
            className="select-field text-sm"
          >
            {symbolOptions.map((s) => (
              <option key={s.symbol} value={s.symbol}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        {/* Side */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Side</label>
          <div className="flex gap-1">
            {ORDER_SIDES.map((side) => (
              <button
                key={side}
                type="button"
                onClick={() => updateField('side', side)}
                className={`flex-1 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${
                  form.side === side
                    ? side === 'buy'
                      ? 'bg-green-500/20 text-green-400 border border-green-500/40'
                      : 'bg-red-500/20 text-red-400 border border-red-500/40'
                    : 'bg-surface text-gray-500 border border-surface-border hover:text-gray-300'
                }`}
              >
                {side}
              </button>
            ))}
          </div>
        </div>

        {/* Type */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Type</label>
          <select
            value={form.type}
            onChange={(e) => updateField('type', e.target.value)}
            className="select-field text-sm"
          >
            {ORDER_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace('_', ' ').toUpperCase()}
              </option>
            ))}
          </select>
        </div>

        {/* Quantity */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Quantity</label>
          <input
            type="number"
            step="any"
            min="0"
            value={form.quantity}
            onChange={(e) => updateField('quantity', e.target.value)}
            placeholder="0.00"
            className={`input-field text-sm font-mono ${errors.quantity ? 'ring-2 ring-red-500/50' : ''}`}
          />
          {errors.quantity && <p className="text-red-400 text-[10px] mt-0.5">{errors.quantity}</p>}
        </div>

        {/* Price */}
        {(form.type === 'limit' || form.type === 'stop_limit') && (
          <div>
            <label className="block text-xs text-gray-500 mb-1">Price</label>
            <input
              type="number"
              step="any"
              min="0"
              value={form.price}
              onChange={(e) => updateField('price', e.target.value)}
              placeholder="0.00"
              className={`input-field text-sm font-mono ${errors.price ? 'ring-2 ring-red-500/50' : ''}`}
            />
            {errors.price && <p className="text-red-400 text-[10px] mt-0.5">{errors.price}</p>}
          </div>
        )}

        {/* Stop Price */}
        {(form.type === 'stop' || form.type === 'stop_limit') && (
          <div>
            <label className="block text-xs text-gray-500 mb-1">Stop Price</label>
            <input
              type="number"
              step="any"
              min="0"
              value={form.stop_price}
              onChange={(e) => updateField('stop_price', e.target.value)}
              placeholder="0.00"
              className={`input-field text-sm font-mono ${errors.stop_price ? 'ring-2 ring-red-500/50' : ''}`}
            />
            {errors.stop_price && (
              <p className="text-red-400 text-[10px] mt-0.5">{errors.stop_price}</p>
            )}
          </div>
        )}

        {/* Time in Force */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Time in Force</label>
          <select
            value={form.time_in_force}
            onChange={(e) => updateField('time_in_force', e.target.value)}
            className="select-field text-sm"
          >
            {TIME_IN_FORCES.map((tif) => (
              <option key={tif} value={tif}>
                {tif.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <p className="text-[10px] text-gray-600">
          Exchange: <span className="text-gray-500">{form.exchange}</span>
        </p>
        <button
          type="submit"
          disabled={createOrder.isPending}
          className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-colors ${
            form.side === 'buy'
              ? 'bg-green-600 hover:bg-green-700 text-white'
              : 'bg-red-600 hover:bg-red-700 text-white'
          } disabled:opacity-50`}
        >
          <Send className="h-4 w-4" />
          {createOrder.isPending
            ? 'Submitting...'
            : `${form.side === 'buy' ? 'Buy' : 'Sell'} ${
                symbolOptions.find((s) => s.symbol === form.symbol)?.label ?? form.symbol
              }`}
        </button>
      </div>
    </form>
  );
}
