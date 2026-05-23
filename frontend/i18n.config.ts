export default defineI18nConfig(() => ({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      common: {
        noData: 'No data available',
        loading: 'Loading...',
        total: 'Total',
        percent: '{value}%',
        revenueUsd: 'Revenue (USD)',
        nothing: 'Nothing',
        search: 'Search...'
      },
      components: {
        select: 'Select...',
        search: 'Search...'
      },
      pages: {
        pos: {
          cart: {
            title: 'Cart',
            clearAll: 'Clear All',
            empty: 'Cart is empty',
            items: 'Items',
            subtotal: 'Subtotal',
            discount: 'Discount',
            total: 'Total',
            finish: 'Finish',
            next: 'Next'
          },
          customer: {
            types: {
              customer: 'Customer',
              walkIn: 'Walk-in'
            },
            form: {
              name: 'Name',
              namePlaceholder: 'Enter name',
              phone: 'Phone',
              phonePlaceholder: 'Enter phone',
              deliveryType: 'Delivery Type',
              deliveryPrice: 'Delivery Price',
              deliveryDate: 'Delivery Date',
              paymentMethod: 'Payment Method',
              deliveryStatus: 'Delivery Status',
              source: 'Source',
              address: 'Address',
              addressPlaceholder: 'Select address',
              statusPending: 'Pending',
              statusDelivered: 'Delivered'
            }
          },
          invoice: {
            title: 'Invoice',
            section: {
              invoiceInfo: 'Invoice Info',
              customer: 'Customer'
            },
            fields: {
              invoiceNo: 'Invoice No',
              date: 'Date',
              deliveryPrice: 'Delivery Price',
              name: 'Name',
              phone: 'Phone',
              deliveryType: 'Delivery Type'
            },
            table: {
              no: 'No.',
              description: 'Description',
              price: 'Price',
              qty: 'Qty',
              total: 'Total'
            },
            terms: {
              title: 'Terms & Conditions',
              en: 'Goods sold are not returnable'
            },
            summary: {
              subtotal: 'Subtotal',
              deliveryPrice: 'Delivery Price',
              discount: 'Discount',
              grandTotal: 'Grand Total'
            },
            footer: {
              customer: 'Customer Signature',
              seller: 'Seller Signature'
            }
          },
          productCard: {
            inStock: 'in stock',
            addMore: 'Add More',
            addToCart: 'Add to Cart'
          }
        },
        provinces: {
          'phnom-penh': 'Phnom Penh',
          'siem-reap': 'Siem Reap',
          'preah-sihanouk': 'Preah Sihanouk',
          'battambang': 'Battambang',
          'kampot': 'Kampot',
          'kep': 'Kep',
          'kandal': 'Kandal',
          'kampong-cham': 'Kampong Cham',
          'kampong-chhnang': 'Kampong Chhnang',
          'kampong-speu': 'Kampong Speu',
          'kampong-thom': 'Kampong Thom',
          'koh-kong': 'Koh Kong',
          'kratie': 'Kratie',
          'mondulkiri': 'Mondulkiri',
          'oddar-meanchey': 'Oddar Meanchey',
          'pailin': 'Pailin',
          'preah-vihear': 'Preah Vihear',
          'prey-veng': 'Prey Veng',
          'pursat': 'Pursat',
          'ratanakiri': 'Ratanakiri',
          'stung-treng': 'Stung Treng',
          'svay-rieng': 'Svay Rieng',
          'takeo': 'Takeo',
          'tbong-khmum': 'Tbong Khmum'
        }
      }
    }
  }
}))
