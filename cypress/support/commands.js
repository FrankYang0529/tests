import cookie from 'cookie';
import addContext from "mochawesome/addContext";

import { Constants } from '../constants/constants'

const path = require('path')

const constants = new Constants();

require('cy-verify-downloads').addCustomCommand();

Cypress.Commands.add('login', (params = {}) => {
    const url = params.url || constants.dashboardUrl;
    const username = params.username ||   Cypress.env('username');
    const password = params.password || Cypress.env('password');

    const isDev = Cypress.env('NODE_ENV') === 'dev';
    const baseUrl = isDev ? Cypress.config('baseUrl') : `${Cypress.config('baseUrl')}/dashboard`;
    cy.intercept('GET', '/v3-public/authProviders').as('authProviders');
    cy.visit(`/auth/login`);
    cy.wait('@authProviders').then(res => {
      const { CSRF } = cookie.parse(document.cookie);
      cy.request({
        method: 'POST',
        url: '/v3-public/localProviders/local?action=login',
        body: {
          description:"UI session",
          responseType:"cookie",
          username,
          password
        },
        headers: {
          'x-api-csrf': CSRF
        }
      }).then(() => {
        cy.visit(url); // After successful login, you can switch to the specified page, which is the home page by default
        cy.get('.initial-load-spinner', { timeout: constants.timeout.maxTimeout })
        cy.get(".dashboard-content .product-name").contains("Harvester")
      });
    })
});

Cypress.Commands.add('stopOnFailed', () => {
  Cypress.on('fail', (e, test) => {
    Cypress.runner.stop();
    throw new Error(e.message);
  })
})

Cypress.Commands.overwrite('visit', (originalFn, url = '', options) => {
  const isDev = Cypress.env('NODE_ENV') === 'dev';

  if (!isDev) {
    url = `/dashboard${url}`;
  }

  return originalFn(url, options)
})


Cypress.on('uncaught:exception', (err, runable) => {
  return false;
})

Cypress.on("test:after:run", (test, runnable) => {  
  if (test.state === "failed") {   
    const dir = Cypress.spec.relative
    const specDir = dir.split('/').slice(1, -1).join('/') 

    let describe = ''
    let context = ''
    let it = test.title

    let fileName = '' 

    if (runnable.parent?.parent?.title) {
      describe = runnable.parent.parent.title
      context = runnable.parent.title
      
      fileName = `${describe} -- ${context} -- ${it} (failed).png`
    } else {
      describe = runnable.parent.title

      fileName = `${runnable.parent.title} -- ${test.title} (failed).png`
    }

    const screenshot =`assets/${specDir}/${Cypress.spec.name}/${fileName}`;    
    
    addContext({ test }, screenshot);  
  }
});
